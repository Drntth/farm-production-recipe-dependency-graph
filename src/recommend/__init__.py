"""
Level recommendations: the combined plan of every level's default profile.

``python -m src recommend`` writes one JSON and one SVG per level for the
static web site; see ``build.py``.
"""

from .build import DEFAULT_LEVELS, level_recommendation, recommendations

__all__ = ["DEFAULT_LEVELS", "level_recommendation", "recommendations"]
