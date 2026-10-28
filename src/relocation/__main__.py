"""Allow running the relocation plan as ``python -m src.relocation``."""

import sys

from .cli import main

sys.exit(main())
