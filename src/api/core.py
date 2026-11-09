"""
Core API: the tools without file IO, dicts in and dicts out.

Every entry point takes the data set (a ``DataSet`` or a data bundle object,
``python -m src bundle``) and the inputs either as models or as parsed JSON
objects (the player profile, the farm map, the settings, the
design templates by name) and returns::

    {"result": <the main JSON output>, "files": {"<path>": "<text>", ...}}

``files`` holds every output file of the tool with exactly the text the CLI
writes (``layout.json``, ``layout.md``, ``layout.svg``, ``blocks/<id>.svg``,
…); paths are relative to the output directory. The CLI loads the inputs,
calls an entry point and writes ``files``; the web app calls the same entry
points in the browser. Progress and warnings go to the tools' loggers
(``src.layout``, ``src.planner``, ``src.combiner``, ``src.relocation``).

*output_dir* is only a hint for the SVGs: the link to the farm map
background image is made relative to it. Nothing is read or written.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.combiner.combine import combine
from src.combiner.report import combined_to_dict, combined_to_markdown
from src.config import PlayerConfig, validate_player_config
from src.layout.describe import layout_to_dict, layout_to_markdown
from src.layout.farm_map import FarmMap
from src.layout.planner import STRATEGIES, Layout, plan_layout
from src.layout.render_svg import render_svg
from src.layout.templates import BlockTemplate, DesignTemplate, resolve_templates
from src.layout.visuals import block_images
from src.loaders.json_loader import DataSet, dataset_from_bundle
from src.planner.run import run_planner
from src.planner.schedule import schedule_to_markdown
from src.relocation.relocate import layout_part, plan_relocation
from src.relocation.report import (
    new_slot_note,
    relocation_to_dict,
    relocation_to_markdown,
)
from src.settings import DesignSettings, PlannerSettings

Json = dict[str, Any]
Templates = dict[str, DesignTemplate | Json]
Data = DataSet | Json  # a DataSet or a data bundle object

layout_log = logging.getLogger("src.layout")
planner_log = logging.getLogger("src.planner")
combiner_log = logging.getLogger("src.combiner")
relocation_log = logging.getLogger("src.relocation")

LAYOUT_STEM = "layout"
COMBINED_STEM = "combined"


# ----------------------------------------------------------------------
# Inputs: a model or its parsed JSON
# ----------------------------------------------------------------------


def _data(data: Data) -> DataSet:
    return data if isinstance(data, DataSet) else dataset_from_bundle(data)


def _player(player: PlayerConfig | Json | None) -> PlayerConfig | None:
    if player is None or isinstance(player, PlayerConfig):
        return player
    return PlayerConfig.model_validate(player)


def _design(design: DesignSettings | Json | None) -> DesignSettings:
    if isinstance(design, DesignSettings):
        return design
    return DesignSettings.model_validate(design or {})


def _planner(planner: PlannerSettings | Json | None) -> PlannerSettings:
    if isinstance(planner, PlannerSettings):
        return planner
    return PlannerSettings.model_validate(planner or {})


def _farm_map(farm_map: FarmMap | Json | None) -> FarmMap:
    if isinstance(farm_map, FarmMap):
        return farm_map
    return FarmMap.model_validate(farm_map or {})


def _templates(
    design: DesignSettings, templates: Templates | None
) -> dict[str, BlockTemplate]:
    return resolve_templates(design.templates, templates or {})


def _player_with_level(
    player: PlayerConfig | Json | None, level: int | None
) -> PlayerConfig:
    """The profile with *level* applied; a bare profile when there is none."""
    p = _player(player)
    if p is None:
        if level is None:
            raise ValueError("No player config and no level given")
        return PlayerConfig(level=level)
    if level is not None:
        p = p.model_copy(update={"level": level})
    return p


def _dump(payload: Json) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _svg_path(output_dir: Path | str | None, name: str) -> Path | None:
    return Path(output_dir) / name if output_dir is not None else None


def _check_level(level: int | None) -> None:
    if level is not None and level < 1:
        raise ValueError("level must be at least 1")


# ----------------------------------------------------------------------
# Layout Planner
# ----------------------------------------------------------------------


def _plan(data, level, player, farm_map, settings: DesignSettings, strategy, templates):
    return plan_layout(
        data,
        level=level,
        player=player,
        farm_map=farm_map,
        reserve_ratio=settings.reserve,
        gap=settings.gap,
        field_pool=settings.field_pool,
        strategy=strategy,
        design=settings.design_layer,
        decor_band=settings.decor_band,
        item_gap=settings.item_gap,
        path_style=settings.path_style,
        path_targets=settings.path_targets,
        design_zones=settings.design_zones,
        main_path_style=settings.main_path_style,
        main_path_width=settings.main_path_width,
        templates=templates,
    )


def layout_stems(settings: DesignSettings) -> list[tuple[str, str]]:
    """(output file stem, strategy); ``all`` adds one file set per strategy."""
    runs = [(LAYOUT_STEM, "auto" if settings.strategy == "all" else settings.strategy)]
    if settings.strategy == "all":
        runs += [(f"layout_{s}", s) for s in STRATEGIES if s != "auto"]
    return runs


def _layout_files(
    layout: Layout, stem: str, payload: Json, output_dir: Path | str | None
) -> dict[str, str]:
    return {
        f"{stem}.json": _dump(payload),
        f"{stem}.md": layout_to_markdown(layout),
        f"{stem}.svg": render_svg(
            layout, href_from=_svg_path(output_dir, f"{stem}.svg")
        ),
    }


def _block_image_files(
    layout: Layout, directory: str, output_dir: Path | str | None
) -> dict[str, str]:
    images = block_images(layout, _svg_path(output_dir, directory))
    return {f"{directory}/{name}": svg for name, svg in images.items()}


def _log_layout_summary(layout: Layout) -> None:
    if layout.design is not None:
        d = layout.design
        layout_log.info(
            "Design: %d path tiles, %d decoration tiles%s%s",
            len(d.paths),
            len(d.decorations),
            f"; to connection point: {', '.join(sorted(d.approached))}"
            if d.approached
            else "",
            f"; not reachable: {', '.join(d.unreachable)}" if d.unreachable else "",
        )
    ext = layout.extent()
    layout_log.info(
        "Farm level %d: %d blocks on %d x %d tiles",
        layout.level,
        len(layout.blocks),
        ext.w,
        ext.h,
    )
    for pb in layout.blocks:
        layout_log.info("  %s: %s", pb.block.name, ", ".join(pb.block.locations))


def layout_plan(
    data: Data,
    *,
    player: PlayerConfig | Json | None = None,
    level: int | None = None,
    farm_map: FarmMap | Json | None = None,
    design: DesignSettings | Json | None = None,
    templates: Templates | None = None,
    output_dir: Path | str | None = None,
) -> Json:
    """
    Farm layout of the unfiltered *data* (``python -m src layout``).

    *level* overrides the profile level; without a profile it is required.
    ``files``: ``layout.*`` (plus ``layout_<strategy>.*`` for strategy
    ``all``) and ``blocks/*.svg`` with the setting ``block_images``.
    Raises ``ValueError`` for invalid inputs or a layout that cannot be made.
    """
    _check_level(level)
    data = _data(data)
    settings = _design(design)
    p = _player(player)
    if p is None and level is None:
        raise ValueError("No player config and no level given")
    fm = _farm_map(farm_map)
    tpl = _templates(settings, templates)
    lvl = level if level is not None else p.level
    if p is not None:
        for problem in validate_player_config(p, data):
            layout_log.warning("Player config: %s", problem)

    filtered = data.filter_by_max_level(lvl)
    files: dict[str, str] = {}
    result: Json = {}
    main_layout: Layout | None = None
    for stem, strategy in layout_stems(settings):
        try:
            layout = _plan(filtered, lvl, p, fm, settings, strategy, tpl)
        except ValueError as exc:
            raise ValueError(f"{stem} (strategy {strategy}): {exc}") from exc
        payload = layout_to_dict(layout) | {"settings": settings.model_dump()}
        files |= _layout_files(layout, stem, payload, output_dir)
        if stem == LAYOUT_STEM:
            main_layout, result = layout, payload
        layout_log.info(
            "%s: strategy %s (used: %s), reserve %.0f%%, %d blocks not placed",
            stem,
            strategy,
            layout.strategy,
            layout.reserve_ratio * 100,
            len(layout.unplaced_blocks),
        )
    if settings.block_images:  # of the main layout
        files |= _block_image_files(main_layout, "blocks", output_dir)
    _log_layout_summary(main_layout)
    return {"result": result, "files": files}


# ----------------------------------------------------------------------
# Production Planner
# ----------------------------------------------------------------------


def production_plan(
    data: Data,
    *,
    player: PlayerConfig | Json | None = None,
    level: int | None = None,
    planner: PlannerSettings | Json | None = None,
) -> Json:
    """
    Production plan of the unfiltered *data* (``python -m src plan``).

    ``result``: the ``schedule.json`` payload; ``files``: ``capacity.json``,
    ``schedule.json``, ``schedule.md``. Raises ``RuntimeError`` when the
    linear program cannot be solved, ``ValueError`` for invalid inputs.
    """
    _check_level(level)
    data = _data(data)
    production = _planner(planner).production
    p = _player_with_level(player, level)
    for problem in validate_player_config(p, data):
        planner_log.warning("Player config: %s", problem)

    filtered = data.filter_by_max_level(p.level)
    run = run_planner(
        p,
        filtered,
        login_window=production.login_window,
        storage_share=production.storage_share,
        min_efficiency=production.min_efficiency,
    )
    for name in run.profile.missing():
        planner_log.warning(
            "Player config: %s is not set; storage limits are unknown", name
        )
    capacity, chosen, schedule = run.capacity, run.chosen, run.schedule
    for warning in chosen.warnings:
        planner_log.warning("Plan: %s", warning)

    result = schedule | {"settings": production.model_dump()}
    files = {
        "capacity.json": _dump(capacity.to_dict()),
        "schedule.json": _dump(result),
        "schedule.md": schedule_to_markdown(schedule, filtered),
    }

    planner_log.info(
        "Level %d: barn %s, silo %s, %s fields (%s)",
        capacity.level,
        capacity.barn_capacity,
        capacity.silo_capacity,
        capacity.fields,
        capacity.fields_source,
    )
    planner_log.info(
        "%d logins a day (longest gap %g h): %.1f production hours per hour, "
        "%.2f spare per good and day, %d of %s fields used",
        chosen.logins,
        max(chosen.login_gaps),
        chosen.busy_hours_per_hour,
        chosen.balance_per_hour * 24,
        round(chosen.fields_used),
        capacity.fields,
    )
    rec = schedule["recommendations"]["trees_and_bushes"]
    recommended = {k: v["plants"] for k, v in rec.items() if v["source"] != "profile"}
    if recommended:
        planner_log.info("Recommended trees / bushes: %s", recommended)
    if chosen.external_per_hour:
        planner_log.info(
            "Needed from outside the plan: %s",
            ", ".join(sorted(chosen.external_per_hour)),
        )
    return {"result": result, "files": files}


# ----------------------------------------------------------------------
# Combiner
# ----------------------------------------------------------------------


def combined_plan(
    data: Data,
    *,
    player: PlayerConfig | Json | None = None,
    level: int | None = None,
    farm_map: FarmMap | Json | None = None,
    design: DesignSettings | Json | None = None,
    planner: PlannerSettings | Json | None = None,
    templates: Templates | None = None,
    data_max_level: int | None = None,
    output_dir: Path | str | None = None,
) -> Json:
    """
    Layout sized by the production plan (``python -m src combine``).

    *data* is unfiltered (the lookahead needs later unlocks);
    *data_max_level* is the highest level the data covers (``meta.json``;
    taken from a data bundle's ``meta`` when not given).
    ``files``: ``combined.json``, ``.md``, ``.svg`` and, with the setting
    ``block_images``, ``combined_blocks/*.svg``. Raises ``RuntimeError`` or
    ``ValueError`` like :func:`production_plan` and :func:`layout_plan`.
    """
    _check_level(level)
    if data_max_level is None and not isinstance(data, DataSet):
        data_max_level = (data.get("meta") or {}).get("max_level")
    data = _data(data)
    settings = _design(design)
    planner_settings = _planner(planner)
    production, combiner = planner_settings.production, planner_settings.combiner
    p = _player_with_level(player, level)
    fm = _farm_map(farm_map)
    tpl = _templates(settings, templates)
    for issue in validate_player_config(p, data):
        combiner_log.warning("Player config: %s", issue)
    if data_max_level is not None and p.level + combiner.lookahead > data_max_level:
        combiner_log.info(
            "The data covers levels up to %d; unlocks above it are not known yet",
            data_max_level,
        )

    combined = combine(
        data,
        p,
        fm,
        lookahead=combiner.lookahead,
        login_window=production.login_window,
        storage_share=production.storage_share,
        min_efficiency=production.min_efficiency,
        reserve_ratio=settings.reserve,
        gap=settings.gap,
        strategy=combiner.strategy,
        design=settings.design_layer,
        decor_band=settings.decor_band,
        item_gap=settings.item_gap,
        path_style=settings.path_style,
        path_targets=settings.path_targets,
        design_zones=settings.design_zones,
        main_path_style=settings.main_path_style,
        main_path_width=settings.main_path_width,
        templates=tpl,
    )
    for name in combined.run.profile.missing():
        combiner_log.warning(
            "Player config: %s is not set; storage limits are unknown", name
        )
    for warning in combined.warnings:
        combiner_log.warning("%s", warning)

    filtered = combined.dataset
    result = combined_to_dict(combined, filtered) | {
        "settings": {
            "design": settings.model_dump(),
            "production": production.model_dump(),
            "combiner": combiner.model_dump(),
        }
    }
    files = {
        f"{COMBINED_STEM}.json": _dump(result),
        f"{COMBINED_STEM}.md": combined_to_markdown(combined, filtered),
        f"{COMBINED_STEM}.svg": render_svg(
            combined.layout,
            href_from=_svg_path(output_dir, f"{COMBINED_STEM}.svg"),
        ),
    }
    if settings.block_images:
        files |= _block_image_files(
            combined.layout, f"{COMBINED_STEM}_blocks", output_dir
        )

    layout, plan = combined.layout, combined.run.chosen
    combiner_log.info(
        "Level %d: %d logins a day, %d blocks (%d not placed), strategy %s, "
        "reserve %.0f%%",
        combined.level,
        plan.logins,
        len(layout.blocks),
        len(layout.unplaced_blocks),
        layout.strategy,
        layout.reserve_ratio * 100,
    )
    if combined.flow_links:
        top = combined.flow_links[0]
        combiner_log.info(
            "Heaviest flow: %s → %s, %.1f goods/h, %s tiles apart",
            top.source,
            top.target,
            top.per_hour,
            "-" if top.distance is None else top.distance,
        )
    return {"result": result, "files": files}


# ----------------------------------------------------------------------
# Relocation plan
# ----------------------------------------------------------------------


def relocation_plan(
    data: Data,
    *,
    layout: Json,
    farm_map: FarmMap | Json | None = None,
    layout_name: str = "layout",
) -> Json:
    """
    Keep / store / place lists from the current farm to *layout*.

    *layout* is a parsed ``layout.json`` or ``combined.json`` (or its layout
    part); *layout_name* names it in the report. ``files``:
    ``relocation.json``, ``relocation.md``. Raises ``ValueError``.
    """
    data = _data(data)
    part = layout_part(layout, layout_name)
    fm = _farm_map(farm_map)
    if not fm.current:
        relocation_log.warning(
            "The farm map has no current farm: measure it in tools/farm_map_editor.html"
        )
    plan = plan_relocation(part, fm, data)
    result = relocation_to_dict(plan, layout_name)
    files = {
        "relocation.json": _dump(result),
        "relocation.md": relocation_to_markdown(plan, layout_name),
    }
    relocation_log.info(
        "Relocation to %s: keep %d, store %d, place %d, reserved %d",
        layout_name,
        len(plan.keep),
        sum(c.count for c in plan.store),
        len(plan.place),
        len(plan.reserved),
    )
    if note := new_slot_note(plan):
        relocation_log.info("%s", note)
    return {"result": result, "files": files}
