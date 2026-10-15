"""Allow running every tool as ``python -m src <command>``."""

import sys

from .cli import main

sys.exit(main())
