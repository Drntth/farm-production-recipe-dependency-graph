"""
Core API: entry points without file IO (dicts in, dicts out).

The CLIs and the web app call these; see ``core.py``. ``write_files`` is the
CLI side: it writes the ``files`` of a result into an output directory.
"""

from .core import combined_plan, layout_plan, production_plan, relocation_plan
from .output import write_files

__all__ = [
    "combined_plan",
    "layout_plan",
    "production_plan",
    "relocation_plan",
    "write_files",
]
