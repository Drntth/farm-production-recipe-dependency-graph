"""
Build-time files of the browser planner (Pyodide worker).

Usage
-----
    python -m src web-files                       # → web/public/py/
    python -m src web-files --output-dir some/dir

Writes ``core.zip`` (the ``src`` modules ``src.api.browser`` needs, found by
following the imports), ``data_bundle.json`` (``python -m src bundle``) and
``defaults.json`` (the level defaults of levels 1 to the data's max level)::

    {"schema_version": 2, "locations": {"<id>": {"name", "type",
        "animal_capacity"?, "max_slots"?}},
     "levels": {"<N>": <level-default player profile>},
     "limits": {"<N>": {"fields": <int>|null, "copies": {"<id>": <int>}}}}

``limits`` are the bounds of the farm profile form per level: the fields
granted and the copies unlocked (``level_limits.json``).

The files are generated and git-ignored.
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import zipfile
from pathlib import Path

from src.api.browser import level_defaults
from src.config import MAX_SLOTS_PER_COPY
from src.loaders.bundle import build_bundle
from src.loaders.json_loader import data_directory, dataset_from_bundle

logger = logging.getLogger("src.recommend")

SRC = Path(__file__).resolve().parents[1]
ENTRY = "src.api.browser"
DEFAULT_OUTPUT = Path("web") / "public" / "py"
_FIXED_TIME = (2020, 1, 1, 0, 0, 0)  # the zip does not change between runs


def _module_file(name: str) -> Path | None:
    """The file of module *name* under src/ (a package: its ``__init__.py``)."""
    path = SRC.parent.joinpath(*name.split("."))
    if path.with_suffix(".py").is_file():
        return path.with_suffix(".py")
    if (path / "__init__.py").is_file():
        return path / "__init__.py"
    return None


def _imports(name: str, path: Path) -> set[str]:
    """Names of the ``src`` modules (and packages) the file imports."""
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join(parts + ([base] if base else []))
            found.add(base)
            found |= {f"{base}.{a.name}" for a in node.names}  # a submodule?
    return {n for n in found if n == "src" or n.startswith("src.")}


def core_files(entry: str = ENTRY) -> dict[str, Path]:
    """Archive path (``src/...``) -> file of every module *entry* needs."""
    todo, seen = [entry], set()
    files: dict[str, Path] = {}
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        parts = name.split(".")
        todo += [".".join(parts[:i]) for i in range(1, len(parts))]  # its packages
        path = _module_file(name)
        if path is None:  # an imported name, not a module
            continue
        files[path.relative_to(SRC.parent).as_posix()] = path
        todo += sorted(_imports(name, path))
    return dict(sorted(files.items()))


def write_core_zip(target: Path, entry: str = ENTRY) -> list[str]:
    """Write the zip of :func:`core_files`; returns its archive paths."""
    files = core_files(entry)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for arcname, path in files.items():
            info = zipfile.ZipInfo(arcname, _FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
    return list(files)


def build_defaults(bundle: dict, levels: range) -> dict:
    """The level defaults and form limits of *levels*; location facts are shared."""
    data = dataset_from_bundle(bundle)
    locations: dict[str, dict] = {}
    profiles: dict[str, dict] = {}
    for level in levels:
        one = level_defaults(bundle, level)
        locations |= one["locations"]
        profiles[str(level)] = one["profile"]
    for loc_id, entry in locations.items():
        loc = data.locations[loc_id]
        if loc.animal_capacity is not None:
            entry["animal_capacity"] = loc.animal_capacity
        if loc.base_slots is not None:
            entry["max_slots"] = loc.max_slots or MAX_SLOTS_PER_COPY
    grants = data.level_limits
    ids = sorted({i.location_id for i in grants.location_instances}) if grants else []
    limits = {
        str(level): {
            "fields": grants.fields_at(level) if grants else None,
            "copies": {i: grants.instances_at(i, level) for i in ids},
        }
        for level in levels
    }
    return {
        "schema_version": 2,
        "locations": locations,
        "levels": profiles,
        "limits": limits,
    }


def _dump(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Write core.zip, data_bundle.json and defaults.json for the "
        "browser planner."
    )
    parser.add_argument("--data-dir", type=data_directory, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    data_log = logging.getLogger("src.loaders")  # one info line per level
    data_log.setLevel(logging.WARNING)
    try:
        bundle = build_bundle(args.data_dir)
        max_level = (bundle.get("meta") or {}).get("max_level")
        if not isinstance(max_level, int):
            raise ValueError("meta.json has no max_level")  # noqa: TRY004
        defaults = build_defaults(bundle, range(1, max_level + 1))
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Cannot build the web files: %s", exc)
        return 1
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    modules = write_core_zip(out / "core.zip")
    (out / "data_bundle.json").write_text(_dump(bundle), encoding="utf-8")
    (out / "defaults.json").write_text(_dump(defaults), encoding="utf-8")
    logger.info(
        "Wrote %d modules, bundle and defaults (levels 1-%d) → %s",
        len(modules),
        max_level,
        out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
