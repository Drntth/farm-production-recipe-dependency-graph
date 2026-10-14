"""Allow running the Production Planner as ``python -m src.planner``."""

import sys

from .cli import main

sys.exit(main())
