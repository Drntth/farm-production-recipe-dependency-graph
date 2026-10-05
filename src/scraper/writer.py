"""Write the three JSON data files and their metadata."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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


def write_meta_file(
    output_dir: Path,
    *,
    max_level: int,
    wiki_revisions: dict[str, str | None],
    known_game_version: str | None = None,
) -> Path:
    """
    Write meta.json describing where and when the data came from.

    Used by the game update checklist (README) to see whether the
    scraped data is older than the latest wiki edits or game update.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "max_level": max_level,
        "known_game_version": known_game_version,
        "wiki_revisions": dict(sorted(wiki_revisions.items())),
    }
    path = output_dir / "meta.json"
    path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {path}")
    return path
