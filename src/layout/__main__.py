"""Allow running the Layout Planner as ``python -m src.layout``."""

import sys

from .cli import main

sys.exit(main())
