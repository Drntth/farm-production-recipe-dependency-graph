"""
Block sizes from production quantities.

The Layout Planner never imports the Production Planner. The Combiner turns a
production plan into this plain input, and ``plan_layout(sizing=...)`` uses it
instead of the profile / level estimates:

- ``counts``: copies to place per location (e.g. recommended trees / bushes);
- ``crop_fields`` and ``crop_use``: fields per crop and which locations use the
  crop, so every block gets the fields its own buildings need;
- ``flows``: goods per hour from a producing to a consuming location; they
  strengthen the pull between the blocks that exchange the most goods;
- ``extra_reserved``: copies to keep free space for (unlocks of later levels).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Sizing:
    counts: dict[str, int] = field(default_factory=dict)
    crop_fields: dict[str, int] = field(default_factory=dict)
    crop_use: dict[str, dict[str, float]] = field(default_factory=dict)
    flows: dict[tuple[str, str], float] = field(default_factory=dict)
    extra_reserved: dict[str, int] = field(default_factory=dict)
