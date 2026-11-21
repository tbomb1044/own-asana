"""Exit 0 if this Python is new enough for own-asana (3.8 or later), else 1."""
import sys

sys.exit(0 if sys.version_info >= (3, 8) else 1)
