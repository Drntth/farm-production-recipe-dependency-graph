"""docs/architecture.md: the package diagram matches the real imports."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DOC = ROOT / "docs" / "architecture.md"
# modules that only dispatch or re-export; the diagram leaves them out
SKIPPED = {"__init__", "__main__", "cli"}
# "graph" is a Mermaid keyword, so the diagram names that node differently
NODE_IDS = {"dgraph": "graph"}


def _part(path: Path) -> str:
    """Top-level package or module name under src/."""
    return path.relative_to(SRC).parts[0].removesuffix(".py")


def _imported(path: Path, node: ast.ImportFrom | ast.Import) -> set[str]:
    if isinstance(node, ast.Import):
        return {a.name.split(".")[1] for a in node.names if a.name.startswith("src.")}
    if node.level == 0:
        parts = (node.module or "").split(".")
        if parts[0] != "src":
            return set()
        return {parts[1]} if len(parts) > 1 else {a.name for a in node.names}
    base = list(path.relative_to(SRC).parent.parts)
    base = base[: len(base) - (node.level - 1)]
    full = base + (node.module.split(".") if node.module else [])
    return {full[0]} if full else {a.name for a in node.names}


def code_edges() -> set[tuple[str, str]]:
    edges = set()
    for path in SRC.rglob("*.py"):
        me = _part(path)
        if me in SKIPPED:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import | ast.ImportFrom):
                edges |= {(me, m) for m in _imported(path, node) if m != me}
    return edges


def doc_edges() -> set[tuple[str, str]]:
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## Package dependencies", 1)[1].split("## ", 1)[0]
    block = section.split("```mermaid", 1)[1].split("```", 1)[0]
    edges = re.findall(r"^\s*(\w+) --> (\w+)\s*$", block, re.MULTILINE)
    return {(NODE_IDS.get(a, a), NODE_IDS.get(b, b)) for a, b in edges}


def test_package_diagram_matches_imports():
    in_code, in_doc = code_edges(), doc_edges()
    assert in_doc, "no edges parsed from docs/architecture.md"
    assert in_code - in_doc == set(), "imports missing from the diagram"
    assert in_doc - in_code == set(), "diagram arrows without an import"
