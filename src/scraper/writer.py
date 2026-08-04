"""Write the three JSON data files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_files(
    output_dir: Path,
    locations: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    recipes: list[dict[str, Any]],
) -> None:
    """Write locations.json, resources.json and recipes.json."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, data in [
        ("locations.json", locations),
        ("resources.json", resources),
        ("recipes.json", recipes),
    ]:
        path = output_dir / name
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Wrote {path} ({len(data)} items)")
