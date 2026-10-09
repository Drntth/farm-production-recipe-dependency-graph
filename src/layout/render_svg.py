"""
Isometric SVG drawing of a farm layout.

Tile (x, y) maps to the screen like the game's diamond grid: x runs down to
the right (↘, footprint width) and y down to the left (↙, footprint height).
The tile grid is always drawn, because the game's Layout Edit Mode shows
none, and every item footprint is outlined on it.

With a calibrated ``background`` in the farm map, the screenshot of the farm
is drawn under the grid through an affine transform (image pixel → tile →
screen), and the farm plots (expansions) are outlined: locked plots shaded.
Zones: buildable outlined in green, blocked filled in red.
"""

from __future__ import annotations

import os
from html import escape
from pathlib import Path

from .farm_map import outline_segments
from .packing import Rect, bounding_rect
from .planner import Layout

TILE_W = 28  # screen width of one diamond
TILE_H = TILE_W // 2
MARGIN = 40
LEGEND_ROW = 18

# Okabe-Ito based palette, readable on white; cycled for many blocks
PALETTE = (
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#CC79A7",
    "#D55E00",
    "#56B4E9",
    "#8C6D1F",
    "#6A3D9A",
    "#B22222",
    "#2E8B57",
    "#4B5563",
    "#C71585",
    "#1F4E79",
    "#9A6324",
    "#469990",
    "#911EB4",
    "#808000",
    "#E6194B",
)
FIXED_COLOUR = "#6B7280"
UNLOCKED_COLOUR = "#15803D"
LOCKED_COLOUR = "#B91C1C"
FARM_OUTLINE_COLOUR = "#111827"
BUILDABLE_COLOUR = "#16A34A"
BLOCKED_COLOUR = "#DC2626"


def render_svg(layout: Layout, path: Path | str | None = None) -> str:
    """Return the SVG text for *layout*; also write it to *path* if given."""
    ext = layout.extent()
    gx0, gy0 = ext.x - 1, ext.y - 1
    gw, gh = ext.w + 2, ext.h + 2
    if layout.farm_map.bounded:
        gx0, gy0, gw, gh = ext.x, ext.y, ext.w, ext.h

    # screen origin (the grid's top corner) so that its left corner sits at MARGIN
    ox = MARGIN + gh * TILE_W / 2
    oy = MARGIN

    def pt(x: float, y: float) -> tuple[float, float]:
        rx, ry = x - gx0, y - gy0
        return (ox + (rx - ry) * TILE_W / 2, oy + (rx + ry) * TILE_H / 2)

    def poly(r: Rect) -> str:
        corners = [
            pt(r.x, r.y),
            pt(r.x + r.w, r.y),
            pt(r.x + r.w, r.y + r.h),
            pt(r.x, r.y + r.h),
        ]
        return " ".join(f"{a:.1f},{b:.1f}" for a, b in corners)

    width = MARGIN * 2 + (gw + gh) * TILE_W / 2
    grid_h = (gw + gh) * TILE_H / 2
    fixed_lines = _wrap(layout.fixed_unplaced, 8)
    legend_rows = len(layout.blocks) + 2 + len(fixed_lines)
    height = MARGIN * 2 + grid_h + 20 + legend_rows * LEGEND_ROW

    fm = layout.farm_map
    bg = fm.background
    out: list[str] = [
        (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{width:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="sans-serif">'
        ),
        f"<title>Farm layout - level {layout.level}</title>",
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
    ]

    def outline(tiles: set, colour: str, width: float, dash: str = "") -> str:
        d = " ".join(
            "M{:.1f},{:.1f} L{:.1f},{:.1f}".format(*pt(*a), *pt(*b))
            for a, b in outline_segments(tiles)
        )
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        return (
            f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}"'
            f'{dash_attr} stroke-linecap="round"/>'
        )

    # background screenshot, mapped onto the tile grid and cut to the map
    if bg is not None:
        href = _href(fm.background_path(), path)
        m = _image_matrix(bg, pt)
        out.append(
            f'<clipPath id="map-clip"><polygon points="{poly(Rect(gx0, gy0, gw, gh))}"/></clipPath>'
        )
        out.append(
            f'<image href="{escape(href)}" xlink:href="{escape(href)}" '
            f'width="{bg.image_width}" height="{bg.image_height}" clip-path="url(#map-clip)" '
            f'transform="matrix({" ".join(f"{v:.6f}" for v in m)})" preserveAspectRatio="none"/>'
        )

    # tile grid
    grid_colour = "#FFFFFF" if bg is not None else "#D1D5DB"
    out.append(f'<g stroke="{grid_colour}" stroke-width="0.6" stroke-opacity="0.8">')
    for i in range(gw + 1):
        (a, b), (c, d) = pt(gx0 + i, gy0), pt(gx0 + i, gy0 + gh)
        out.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d:.1f}"/>')
    for j in range(gh + 1):
        (a, b), (c, d) = pt(gx0, gy0 + j), pt(gx0 + gw, gy0 + j)
        out.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d:.1f}"/>')
    out.append("</g>")

    # zones: buildable sections, blocked tiles (water, road, …); one outline per zone
    for z in fm.zones:
        blocked = z.kind == "blocked"
        colour = BLOCKED_COLOUR if blocked else BUILDABLE_COLOUR
        if blocked:
            for x, y, w, h in z.cells:
                out.append(
                    f'<polygon points="{poly(Rect(x, y, w, h))}" fill="{colour}" '
                    f'fill-opacity="0.35"><title>{escape(z.id)} ({z.kind})</title></polygon>'
                )
        if z.cells:
            out.append(outline(z.tiles(), colour, 1 if blocked else 2.5))
            box = bounding_rect([Rect(*c) for c in z.cells])
            out.append(_label(pt(*_mid(box)), z.id, 10, colour, bold=True))

    # farm plots (expansions)
    for e in fm.expansions:
        colour = UNLOCKED_COLOUR if e.is_unlocked else LOCKED_COLOUR
        fill = (
            'fill="none"'
            if e.is_unlocked
            else f'fill="{LOCKED_COLOUR}" fill-opacity="0.18"'
        )
        state = "unlocked" if e.is_unlocked else "locked"
        for x, y, w, h in e.cells:
            out.append(
                f'<polygon points="{poly(Rect(x, y, w, h))}" {fill}>'
                f"<title>{escape(e.id)} ({state})</title></polygon>"
            )
        if e.cells:
            out.append(outline(e.tiles(), colour, 1.2, "5,3"))
            box = bounding_rect([Rect(*c) for c in e.cells])
            out.append(_label(pt(*_mid(box)), e.id, 10, colour, bold=True))

    # outline of the whole farm (all plots and buildable zones)
    farm_tiles = fm.farm_tiles()
    if farm_tiles:
        out.append(outline(farm_tiles, FARM_OUTLINE_COLOUR, 3))

    # fixed buildings
    for f in layout.farm_map.placed_fixed:
        r = Rect(f.x, f.y, f.width, f.height)
        out.append(
            f'<polygon points="{poly(r)}" fill="{_tint(FIXED_COLOUR, 0.6)}" '
            f'stroke="{FIXED_COLOUR}" stroke-width="1.5"><title>{escape(f.label)} (fixed)</title></polygon>'
        )
        out.append(_label(pt(*_mid(r)), f.label, 10, "#111827"))

    # blocks and items
    colours = {
        b.block.id: PALETTE[i % len(PALETTE)] for i, b in enumerate(layout.blocks)
    }
    placed = [pb for pb in layout.blocks if pb.frame is not None]
    for pb in placed:
        c = colours[pb.block.id]
        see_through = ' fill-opacity="0.45"' if bg is not None else ""
        out.append(
            f'<polygon points="{poly(pb.frame)}" fill="{_tint(c, 0.92)}"{see_through} '
            f'stroke="{c}" stroke-width="2.5"><title>{escape(pb.block.name)}</title></polygon>'
        )
        for it in pb.items:
            style = (
                f'fill="{_tint(c, 0.9)}" stroke-dasharray="3,2"'
                if it.reserved
                else f'fill="{_tint(c, 0.6)}"'
            )
            tip = f"{it.name} ({it.rect.w}x{it.rect.h})" + (
                " - reserved" if it.reserved else ""
            )
            out.append(
                f'<polygon points="{poly(it.rect)}" {style} stroke="{c}" stroke-width="1">'
                f"<title>{escape(tip)}</title></polygon>"
            )
    # labels last, so no block covers them: one per building, one per patch
    for pb in placed:
        patches: dict[str, list[Rect]] = {}
        for it in pb.items:
            if it.in_patch:
                patches.setdefault(it.name, []).append(it.rect)
            else:
                out.append(_label(pt(*_mid(it.rect)), it.name, 9, "#111827"))
        for name, rects in patches.items():
            box = bounding_rect(rects)
            out.append(_label(pt(*_mid(box)), f"{name} ×{len(rects)}", 9, "#111827"))
    for pb in placed:
        c = colours[pb.block.id]
        out.append(
            _label(pt(pb.frame.x, pb.frame.y), pb.block.name, 12, c, dy=-6, bold=True)
        )

    # legend
    y = MARGIN + grid_h + 30
    out.append(
        _text(
            MARGIN,
            y,
            f"Level {layout.level} · 1 diamond = 1 tile · x ↘ (width), y ↙ (height)"
            " · dashed = reserved copy",
            11,
            "#374151",
        )
    )
    for pb in layout.blocks:
        y += LEGEND_ROW
        c = colours[pb.block.id]
        where = (
            "not placed"
            if pb.frame is None
            else f"{pb.frame.w}x{pb.frame.h} at ({pb.frame.x}, {pb.frame.y})"
        )
        out.append(
            f'<rect x="{MARGIN}" y="{y - 10}" width="12" height="12" fill="{c}"/>'
        )
        out.append(_text(MARGIN + 18, y, f"{pb.block.name}: {where}", 11, "#111827"))
    if fixed_lines:
        y += LEGEND_ROW
        out.append(
            _text(
                MARGIN,
                y,
                "Fixed, position unknown (add to config/farm_map.json):",
                11,
                FIXED_COLOUR,
            )
        )
        for line in fixed_lines:
            y += LEGEND_ROW
            out.append(_text(MARGIN + 18, y, line, 11, FIXED_COLOUR))
    out.append("</svg>")

    svg = "\n".join(out)
    if path is not None:
        Path(path).write_text(svg, encoding="utf-8")
    return svg


def _image_matrix(bg, pt) -> tuple[float, ...]:
    """SVG matrix(a b c d e f) mapping image pixels to screen coordinates."""
    (ax, ay), (bx, by) = bg.x_axis_px, bg.y_axis_px
    det = ax * by - bx * ay
    # tile = inv([[ax, bx], [ay, by]]) @ (p - origin)
    inv = ((by / det, -bx / det), (-ay / det, ax / det))
    o = pt(0, 0)
    sx, sy = pt(1, 0), pt(0, 1)
    S = ((sx[0] - o[0], sy[0] - o[0]), (sx[1] - o[1], sy[1] - o[1]))  # screen per tile
    A = tuple(
        tuple(sum(S[i][k] * inv[k][j] for k in range(2)) for j in range(2))
        for i in range(2)
    )
    ox_, oy_ = bg.origin_px
    e = o[0] - (A[0][0] * ox_ + A[0][1] * oy_)
    f = o[1] - (A[1][0] * ox_ + A[1][1] * oy_)
    return (A[0][0], A[1][0], A[0][1], A[1][1], e, f)


def _href(image: Path, svg_path: Path | str | None) -> str:
    if svg_path is None:
        return image.as_uri()
    rel = os.path.relpath(image, Path(svg_path).resolve().parent)
    return Path(rel).as_posix()


def _wrap(ids: list[str], per_line: int) -> list[str]:
    return [", ".join(ids[i : i + per_line]) for i in range(0, len(ids), per_line)]


def _tint(hex_colour: str, amount: float) -> str:
    """Mix *hex_colour* with white; amount 0 = colour, 1 = white."""
    rgb = [int(hex_colour[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(v + (255 - v) * amount):02X}" for v in rgb)


def _mid(r: Rect) -> tuple[float, float]:
    return (r.x + r.w / 2, r.y + r.h / 2)


def _label(p, text, size, colour, dy=0, bold=False) -> str:
    weight = ' font-weight="bold"' if bold else ""
    return (
        f'<text x="{p[0]:.1f}" y="{p[1] + dy + size / 3:.1f}" font-size="{size}" '
        f'text-anchor="middle" fill="{colour}"{weight}>{escape(text)}</text>'
    )


def _text(x, y, text, size, colour) -> str:
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{colour}">{escape(text)}</text>'
