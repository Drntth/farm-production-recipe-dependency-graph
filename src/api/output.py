"""Write the ``files`` of a Core API result: the one place with file IO here."""

from __future__ import annotations

from pathlib import Path


def write_files(directory: Path | str, files: dict[str, str]) -> list[Path]:
    """
    Write *files* (relative path -> text) below *directory*, UTF-8.

    A subdirectory of SVG images (``blocks/``) is generated as a whole: its
    SVGs of an earlier run are removed first, because a block may be gone.
    """
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    subdirs = {Path(name).parent for name in files} - {Path(".")}
    for sub in sorted(subdirs):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for old in (out / sub).glob("*.svg"):
            old.unlink()
    paths = []
    for name, text in files.items():
        path = out / name
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths
