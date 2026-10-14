"""Allow running the Combiner as ``python -m src.combiner``."""

import sys

from .cli import main

sys.exit(main())
