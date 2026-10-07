"""
Layout Planner (farm): named blocks, footprints, isometric SVG.

Uses only the shared core (config, models, loaders, graph); it never imports
the Production Planner.
"""

from .blocks import Block, detect_named_blocks
from .farm_map import FarmMap, FixedItem, load_farm_map
from .planner import Layout, plan_layout
from .render_svg import render_svg

__all__ = [
    "Block",
    "FarmMap",
    "FixedItem",
    "Layout",
    "detect_named_blocks",
    "load_farm_map",
    "plan_layout",
    "render_svg",
]
