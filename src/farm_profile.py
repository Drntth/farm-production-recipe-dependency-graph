"""
Farm profile: every player-side input of one farm in one JSON file.

    {"schema_version": 1, "name": "...", "player": {...}, "profile_map": {...},
     "design": {...}, "planner": {...}, "templates": {"<name>": {...}}}

Each part has the content of its own file (``config/player.json``,
``config/profile_map.json``, ``config/design.json``, ``config/planner.json``,
``config/templates/<name>.json``), version included. The tools read it with
``--farm-profile PATH`` instead of those files; the farm map is the profile
map merged with ``<data-dir>/base_map.json``. ``python -m src farm-profile``
assembles one from the current files.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field, PrivateAttr

from src.config import PlayerConfig, load_player_config
from src.layout.farm_map import (
    FarmMap,
    ProfileMap,
    default_map_path,
    is_one_file_map,
    load_base_map,
    merge_maps,
    profile_map_json,
    split_map,
)
from src.layout.migrate_map import rebase_background
from src.layout.templates import DesignTemplate, load_template_files
from src.schema import Versioned, stamp
from src.settings import (
    DesignSettings,
    PlannerSettings,
    load_design_settings,
    load_planner_settings,
)

logger = logging.getLogger("src.farm_profile")

DEFAULT_OUTPUT = Path("config") / "farm_profile.json"
# option dest -> option name of the separate input files a farm profile replaces
SEPARATE_OPTIONS = {
    "player_config": "--player-config",
    "farm_map": "--map",
    "design_config": "--design-config",
    "planner_config": "--planner-config",
}


class FarmProfile(Versioned):
    schema_kind = "farm_profile"

    name: str | None = None
    player: PlayerConfig
    profile_map: ProfileMap = Field(default_factory=ProfileMap)
    design: DesignSettings = Field(default_factory=DesignSettings)
    planner: PlannerSettings = Field(default_factory=PlannerSettings)
    templates: dict[str, DesignTemplate] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")
    _base_dir: Path = PrivateAttr(default_factory=Path)

    def farm_map(self, base_map: Path | str) -> FarmMap:
        """The profile map merged with the base map; background next to the file."""
        farm_map = merge_maps(load_base_map(base_map), self.profile_map)
        farm_map._base_dir = self._base_dir
        return farm_map


def load_farm_profile(path: Path | str) -> FarmProfile:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Farm profile not found: {p}")
    profile = FarmProfile.model_validate(json.loads(p.read_text(encoding="utf-8")))
    profile._base_dir = p.parent
    return profile


def farm_profile_of(args: argparse.Namespace) -> FarmProfile | None:
    """
    The ``--farm-profile`` of a tool's arguments, or None without one.

    Raises ``ValueError`` when separate input files are given as well.
    """
    path = getattr(args, "farm_profile", None)
    if path is None:
        return None
    given = [opt for dest, opt in SEPARATE_OPTIONS.items() if getattr(args, dest, None)]
    if given:
        raise ValueError(f"--farm-profile replaces {', '.join(given)}; give only one")
    return load_farm_profile(path)


def farm_profile_json(profile: FarmProfile) -> dict[str, Any]:
    """The JSON object of a farm profile; every part carries its version."""
    player = profile.player.model_dump(mode="json", exclude_none=True)
    player["locations"] = {
        k: {f: v for f, v in p.items() if v is not None}
        for k, p in player.get("locations", {}).items()
    }
    data: dict[str, Any] = {"name": profile.name} if profile.name else {}
    data |= {
        "player": stamp("player", player),
        "profile_map": profile_map_json(profile.profile_map),
        "design": stamp("design", profile.design.model_dump(mode="json")),
        "planner": stamp("planner", profile.planner.model_dump(mode="json")),
        "templates": {
            name: stamp("template", t.model_dump(mode="json"))
            for name, t in profile.templates.items()
        },
    }
    return stamp("farm_profile", data)


def _profile_map(path: Path, base_map: Path) -> ProfileMap:
    """The player's part of a farm map file (a one-file map is split)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not (isinstance(data, dict) and is_one_file_map(data)):
        return ProfileMap.model_validate(data)
    base, profile = split_map(FarmMap.model_validate(data))
    if base_map.exists() and load_base_map(base_map) != base:
        logger.warning(
            "The geometry of %s differs from %s; the farm profile uses %s",
            path,
            base_map,
            base_map,
        )
    return profile


def assemble(args: argparse.Namespace) -> dict[str, Any]:
    """The farm profile JSON from the separate files named in *args*."""
    base_map = args.data_dir / "base_map.json"
    map_path = args.map if args.map is not None else default_map_path()
    design, _ = load_design_settings(args.design_config)
    planner, _ = load_planner_settings(args.planner_config)
    profile = FarmProfile(
        name=args.name,
        player=load_player_config(args.player_config),
        profile_map=_profile_map(map_path, base_map)
        if map_path.exists()
        else ProfileMap(),
        design=design,
        planner=planner,
        templates=load_template_files(design.templates),
    )
    merge_maps(load_base_map(base_map), profile.profile_map)  # plot ids exist
    data = farm_profile_json(profile)
    rebase_background(data["profile_map"], map_path, args.output)
    return data


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Assemble a farm profile from the player, map, settings and "
        "template files."
    )
    parser.add_argument("--player-config", type=Path, default=None)
    parser.add_argument("--map", type=Path, default=None, help="Farm map")
    parser.add_argument("--design-config", type=Path, default=None)
    parser.add_argument("--planner-config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--name", default=None, help="Name of the farm")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="Overwrite the output")
    args = parser.parse_args(argv)
    if args.output.exists() and not args.force:
        logger.error("%s exists; use --force to overwrite it", args.output)
        return 1
    try:
        data = assemble(args)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Cannot assemble the farm profile: %s", exc)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(text, encoding="utf-8")
    logger.info("Wrote %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
