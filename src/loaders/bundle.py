"""
Data bundle: every shared data file in one JSON object.

Usage
-----
    python -m src bundle                         # data/ → output/data_bundle.json
    python -m src bundle --output web/data.json

The bundle holds ``meta.json``, the entity files with ``data/overrides/``
already merged, ``level_limits.json``, ``mastery_bonuses.json`` and
``base_map.json``::

    {"schema_version": 1, "meta": {...}, "locations": [...], "resources": [...],
     "recipes": [...], "level_limits": {...}, "mastery_bonuses": [...],
     "base_map": {...}}

A client without file access (the web app) loads it in one request.
``load_data(<bundle file>)`` and ``dataset_from_bundle(obj)`` read it.
The bundle is generated, not committed: write it again after a re-scrape.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from src.schema import stamp

from .json_loader import dataset_from_raw, read_raw_data

logger = logging.getLogger("src.loaders")

DEFAULT_OUTPUT = Path("output") / "data_bundle.json"


def _optional_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def build_bundle(data_dir: Path | str) -> dict[str, Any]:
    """The bundle object of *data_dir*; the entities are validated first."""
    data_dir = Path(data_dir)
    raw = read_raw_data(data_dir)
    dataset_from_raw(raw)  # a bundle never holds invalid data
    bundle = {"meta": _optional_json(data_dir / "meta.json")} | raw
    bundle["base_map"] = _optional_json(data_dir / "base_map.json")
    return stamp("data_bundle", bundle)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Write every shared data file as one JSON data bundle."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        bundle = build_bundle(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Cannot build the data bundle: %s", exc)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + "\n"
    args.output.write_text(text, encoding="utf-8")
    logger.info("Wrote %s (%d KiB)", args.output, len(text.encode()) // 1024)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
