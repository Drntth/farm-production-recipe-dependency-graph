"""
JSON data loader for locations, resources, recipes and level limits.

Loads the normalised JSON files, merges manual overrides from
``data/overrides/``, validates everything against the Pydantic models,
optionally filters by maximum unlock level, and returns a single DataSet
object ready for graph generation.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.models import LevelLimits, Location, MasteryBonus, Recipe, Resource
from src.schema import upgrade

logger = logging.getLogger(__name__)

OVERRIDES_DIRNAME = "overrides"
Raw = dict[str, Any]


class DataSet:
    """
    In-memory collection of all validated entities.

    Provides fast lookup by id and guarantees referential integrity
    checks (source_location_id, location_id, resource_id references).
    """

    def __init__(
        self,
        locations: list[Location],
        resources: list[Resource],
        recipes: list[Recipe],
        level_limits: LevelLimits | None = None,
        mastery_bonuses: list[MasteryBonus] | None = None,
        *,
        log_external: bool = True,
    ) -> None:
        self.locations: dict[str, Location] = {loc.id: loc for loc in locations}
        self.resources: dict[str, Resource] = {res.id: res for res in resources}
        self.recipes: dict[str, Recipe] = {rec.id: rec for rec in recipes}
        self.level_limits: LevelLimits | None = level_limits
        self.mastery_bonuses: list[MasteryBonus] = list(mastery_bonuses or [])

        self._validate_references(log_external=log_external)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def location_list(self) -> list[Location]:
        return list(self.locations.values())

    @property
    def resource_list(self) -> list[Resource]:
        return list(self.resources.values())

    @property
    def recipe_list(self) -> list[Recipe]:
        return list(self.recipes.values())

    def filter_by_max_level(self, max_level: int) -> DataSet:
        """Return a new DataSet containing only entities with unlock_level <= max_level."""
        locations = [l for l in self.location_list if l.unlock_level <= max_level]
        resources = [r for r in self.resource_list if r.unlock_level <= max_level]
        recipes = [r for r in self.recipe_list if r.unlock_level <= max_level]
        limits = (
            self.level_limits.filter_by_max_level(max_level)
            if self.level_limits is not None
            else None
        )
        kept = {l.id for l in locations}
        bonuses = [b for b in self.mastery_bonuses if b.location_id in kept]
        # the full set already reported its external inputs
        return DataSet(
            locations, resources, recipes, limits, bonuses, log_external=False
        )

    def summary(self) -> str:
        return (
            f"DataSet(locations={len(self.locations)}, "
            f"resources={len(self.resources)}, "
            f"recipes={len(self.recipes)})"
        )

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def external_inputs(self) -> dict[str, list[str]]:
        """Recipe inputs that are not resources (vouchers, diamonds, …) → recipe ids."""
        result: dict[str, list[str]] = {}
        for rec in self.recipes.values():
            for inp in rec.inputs:
                if inp.resource_id not in self.resources:
                    result.setdefault(inp.resource_id, []).append(rec.id)
        return {k: sorted(v) for k, v in sorted(result.items())}

    def _validate_references(self, *, log_external: bool = True) -> None:
        """Raise ValueError if any foreign-key style reference is broken."""
        errors: list[str] = []

        for res in self.resources.values():
            if res.source_location_id and res.source_location_id not in self.locations:
                errors.append(
                    f"Resource '{res.id}' references unknown source_location_id "
                    f"'{res.source_location_id}'"
                )

        for rec in self.recipes.values():
            if rec.location_id not in self.locations:
                errors.append(
                    f"Recipe '{rec.id}' references unknown location_id '{rec.location_id}'"
                )

            if rec.output.resource_id not in self.resources:
                errors.append(
                    f"Recipe '{rec.id}' output references unknown resource_id "
                    f"'{rec.output.resource_id}'"
                )

        if self.level_limits is not None:
            for inst in self.level_limits.location_instances:
                if inst.location_id not in self.locations:
                    errors.append(
                        f"Level limit instance {inst.instance} references unknown "
                        f"location_id '{inst.location_id}'"
                    )

        for bonus in self.mastery_bonuses:
            if bonus.location_id not in self.locations:
                errors.append(
                    f"Mastery bonus references unknown location_id "
                    f"'{bonus.location_id}'"
                )

        external = self.external_inputs()
        if log_external and external:
            logger.info(
                "External recipe inputs (not graph nodes): %s",
                ", ".join(f"{k} ({len(v)})" for k, v in external.items()),
            )

        if errors:
            raise ValueError(
                "Referential integrity errors:\n  - " + "\n  - ".join(errors)
            )


# ----------------------------------------------------------------------
# Loading helpers
# ----------------------------------------------------------------------


def _load_json_file(path: Path) -> list:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        # ValueError on purpose: callers report every bad data file through it
        raise ValueError(  # noqa: TRY004
            f"Expected a JSON array in {path}, got {type(data).__name__}"
        )
    return data


def _parse_entities(raw: list, model_cls, label: str):
    entities = []
    for idx, item in enumerate(raw):
        try:
            entities.append(model_cls.model_validate(item))
        except ValidationError as exc:
            raise ValueError(
                f"Validation error in {label}[{idx}] (id={item.get('id', '?')}):\n{exc}"
            ) from exc
    return entities


def apply_overrides(raw: list[dict], overrides: list[dict], label: str) -> list[dict]:
    """
    Merge manual *overrides* into scraped *raw* entities by ``id``.

    An override with an existing id patches only the fields it lists;
    one with a new id adds a complete entity. ``null`` values mean
    "not filled in yet" and are skipped, so template entries are harmless.
    Order of *raw* is kept.
    """
    by_id = {item["id"]: dict(item) for item in raw}
    patched: list[str] = []
    added: list[str] = []
    for idx, entry in enumerate(overrides):
        oid = entry.get("id")
        if not oid:
            raise ValueError(f"Override {label}[{idx}] has no 'id'")
        override = {k: v for k, v in entry.items() if v is not None}
        if len(override) == 1:  # only the id: nothing filled in yet
            continue
        if oid in by_id:
            by_id[oid].update(override)
            patched.append(oid)
            logger.debug("Override patched %s '%s'", label, oid)
        else:
            by_id[oid] = dict(override)
            added.append(oid)
            logger.debug("Override added %s '%s'", label, oid)
    if patched or added:
        # one line per file; the ids are in the debug log
        logger.info(
            "Overrides for %s: %d patched, %d added%s",
            label,
            len(patched),
            len(added),
            f" ({', '.join(added)})" if added else "",
        )
    return list(by_id.values())


def _load_with_overrides(
    data_dir: Path, filename: str, overrides_dir: Path | None
) -> list[dict]:
    raw = _load_json_file(data_dir / filename)
    if overrides_dir is not None and (overrides_dir / filename).exists():
        overrides = _load_json_file(overrides_dir / filename)
        raw = apply_overrides(raw, overrides, filename.removesuffix(".json"))
    return raw


def _read_level_limits(data_dir: Path) -> dict | None:
    path = data_dir / "level_limits.json"
    if not path.exists():
        logger.info("No level_limits.json in %s", data_dir)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_mastery_bonuses(data_dir: Path) -> list[dict]:
    path = data_dir / "mastery_bonuses.json"
    if not path.exists():
        logger.info("No mastery_bonuses.json in %s", data_dir)
        return []
    return _load_json_file(path)


def read_raw_data(data_dir: Path | str, *, apply_data_overrides: bool = True) -> Raw:
    """
    The data files of *data_dir* as JSON, overrides merged, not validated.

    Keys: ``locations``, ``resources``, ``recipes`` (lists), ``level_limits``
    (object or None), ``mastery_bonuses`` (list).
    """
    data_dir = Path(data_dir)
    overrides_dir = data_dir / OVERRIDES_DIRNAME if apply_data_overrides else None
    raw: Raw = {
        name: _load_with_overrides(data_dir, f"{name}.json", overrides_dir)
        for name in ("locations", "resources", "recipes")
    }
    raw["level_limits"] = _read_level_limits(data_dir)
    raw["mastery_bonuses"] = _read_mastery_bonuses(data_dir)
    return raw


def dataset_from_raw(raw: Raw) -> DataSet:
    """Validate the JSON of :func:`read_raw_data` (or of a data bundle)."""
    limits = raw.get("level_limits")
    try:
        level_limits = None if limits is None else LevelLimits.model_validate(limits)
    except ValidationError as exc:
        raise ValueError(f"Validation error in level_limits:\n{exc}") from exc
    return DataSet(
        _parse_entities(raw["locations"], Location, "locations"),
        _parse_entities(raw["resources"], Resource, "resources"),
        _parse_entities(raw["recipes"], Recipe, "recipes"),
        level_limits,
        _parse_entities(
            raw.get("mastery_bonuses") or [], MasteryBonus, "mastery_bonuses"
        ),
    )


def load_data(
    data_dir: Path | str,
    max_level: int | None = None,
    *,
    apply_data_overrides: bool = True,
) -> DataSet:
    """
    Load and validate the core JSON files from *data_dir*.

    Parameters
    ----------
    data_dir:
        Directory containing ``locations.json``, ``resources.json``,
        ``recipes.json`` and optionally ``level_limits.json`` and
        ``mastery_bonuses.json``; or a data bundle file
        (``python -m src bundle``), which already holds the overrides.
    max_level:
        If given, only entities with ``unlock_level <= max_level`` are kept.
    apply_data_overrides:
        Merge ``<data_dir>/overrides/*.json`` on top of the scraped data.

    Returns
    -------
    DataSet
        Validated, optionally filtered collection of entities.
    """
    data_dir = Path(data_dir)
    if data_dir.is_file():
        logger.info("Loading data bundle %s", data_dir)
        dataset = dataset_from_bundle(json.loads(data_dir.read_text(encoding="utf-8")))
    else:
        logger.info("Loading data from %s", data_dir)
        dataset = dataset_from_raw(
            read_raw_data(data_dir, apply_data_overrides=apply_data_overrides)
        )
    logger.info("Loaded %s", dataset.summary())

    if max_level is not None:
        dataset = dataset.filter_by_max_level(max_level)
        logger.info("After max_level=%s filter: %s", max_level, dataset.summary())

    return dataset


BUNDLE_LISTS = ("locations", "resources", "recipes")


def dataset_from_bundle(bundle: Raw) -> DataSet:
    """The DataSet of a data bundle object (any ``schema_version`` it can read)."""
    if not isinstance(bundle, dict):
        raise ValueError("A data bundle is a JSON object")  # noqa: TRY004
    bundle = upgrade("data_bundle", bundle)
    missing = [k for k in BUNDLE_LISTS if k not in bundle]
    if missing:
        raise ValueError(f"A data bundle needs {', '.join(missing)}")
    wrong = [k for k in BUNDLE_LISTS if not isinstance(bundle[k], list)]
    if not isinstance(bundle.get("mastery_bonuses") or [], list):
        wrong.append("mastery_bonuses")
    if wrong:
        raise ValueError(f"Not a list in the data bundle: {', '.join(wrong)}")
    return dataset_from_raw(bundle)


def data_directory(value: str) -> Path:
    """
    ``--data-dir`` of the tool CLIs: a directory, never a data bundle file.

    The bundle is for the Core API (``dataset_from_bundle``); the CLIs also
    read ``meta.json`` and ``base_map.json`` from the directory.
    """
    path = Path(value)
    if path.is_file():
        raise argparse.ArgumentTypeError(
            f"{path} is a file; --data-dir takes the data directory "
            "(a data bundle is read by the Core API)"
        )
    return path
