"""
Block images: one SVG per block and a collage of every block.

- ``block_layout``: one placed block on its own small grid (the frame plus a
  one-tile margin), with the paths and the decoration band around it, so it
  can be followed in the game block by block.
- ``collage_layout``: every placed block side by side in rows, apart from the
  map, to compare the blocks at a glance.

Both build a small ``Layout`` and reuse ``render_svg``; ``write_block_images``
writes ``<dir>/<block id>.svg`` and ``<dir>/collage.svg`` into a directory of
generated images (the SVGs of an earlier run there are removed first).
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from .design import Design
from .farm_map import FarmMap
from .packing import Rect
from .planner import Layout, PlacedBlock
from .render_svg import render_svg

MARGIN_TILES = 1  # free tiles around a block on its own image
BLOCK_SCALE = 2.0  # block images are small: shown twice as large
COLLAGE_GAP = 2  # tiles between the blocks of the collage


def _moved(pb: PlacedBlock, dx: int, dy: int) -> PlacedBlock:
    f = pb.frame
    return PlacedBlock(
        pb.block,
        Rect(f.x + dx, f.y + dy, f.w, f.h),
        [
            replace(i, rect=Rect(i.rect.x + dx, i.rect.y + dy, i.rect.w, i.rect.h))
            for i in pb.items
        ],
        pb.fields,
    )


def _bare(layout: Layout, width: int, height: int, blocks: list[PlacedBlock]):
    """*layout* reduced to *blocks* on an empty map of the given size."""
    return replace(
        layout,
        farm_map=FarmMap(width=width, height=height),
        blocks=blocks,
        fixed_unplaced=[],
        design=None,
    )


def block_layout(layout: Layout, pb: PlacedBlock) -> Layout:
    """One placed block on its own grid, with the paths around it."""
    if pb.frame is None:
        raise ValueError(f"Block {pb.block.id} is not placed")
    f, m = pb.frame, MARGIN_TILES
    dx, dy = m - f.x, m - f.y
    small = _bare(layout, f.w + 2 * m, f.h + 2 * m, [_moved(pb, dx, dy)])
    d = layout.design
    if d is not None:

        def near(tiles):
            return {
                (x + dx, y + dy)
                for x, y in tiles
                if f.x - m <= x < f.x + f.w + m and f.y - m <= y < f.y + f.h + m
            }

        small.design = Design(
            paths=near(d.paths),
            main_paths=near(d.main_paths),
            lanes=near(d.lanes),
            decorations=near(d.decorations),
            decor_band=d.decor_band,
            path_style=d.path_style,
            main_path_style=d.main_path_style,
            main_path_width=d.main_path_width,
            path_targets=d.path_targets,
        )
    return small


def collage_layout(layout: Layout) -> Layout:
    """Every placed block in rows (largest first), apart from the map."""
    placed = sorted(
        (pb for pb in layout.blocks if pb.frame is not None),
        key=lambda pb: (-pb.frame.w * pb.frame.h, pb.block.id),
    )
    if not placed:
        return _bare(layout, 1, 1, [])
    area = sum((pb.frame.w + COLLAGE_GAP) * (pb.frame.h + COLLAGE_GAP) for pb in placed)
    row_width = max(max(pb.frame.w for pb in placed), math.ceil(math.sqrt(area) * 1.2))
    x = y = row_h = width = 0
    moved = []
    for pb in placed:  # shelf packing: fill a row, then start the next one
        if x and x + pb.frame.w > row_width:
            x, y, row_h = 0, y + row_h + COLLAGE_GAP, 0
        moved.append(_moved(pb, x - pb.frame.x, y - pb.frame.y))
        x += pb.frame.w + COLLAGE_GAP
        row_h = max(row_h, pb.frame.h)
        width = max(width, x - COLLAGE_GAP)
    return _bare(layout, width, y + row_h, moved)


def write_block_images(layout: Layout, directory: Path | str) -> list[Path]:
    """``<block id>.svg`` per placed block and ``collage.svg``; returns the paths."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.svg"):  # a block of an earlier run may be gone
        old.unlink()
    paths = []
    for pb in layout.blocks:
        if pb.frame is None:
            continue
        path = out / f"{pb.block.id}.svg"
        render_svg(
            block_layout(layout, pb),
            path,
            title=f"{pb.block.name} - level {layout.level}",
            scale=BLOCK_SCALE,
            # the legend shows where the block sits on the farm map
            offset=(pb.frame.x - MARGIN_TILES, pb.frame.y - MARGIN_TILES),
        )
        paths.append(path)
    collage = out / "collage.svg"
    render_svg(collage_layout(layout), collage, title=f"Blocks - level {layout.level}")
    paths.append(collage)
    return paths
