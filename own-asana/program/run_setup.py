"""Starts own-asana's setup. Run with: python -I -B run_setup.py [--window | --check]

The options are described in own_asana/entry.py. The token is never one of them.
"""
import os
import sys

# -I leaves this folder off the import path on purpose; add only this folder back.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.version_info < (3, 8):
    sys.stderr.write("own-asana needs Python 3.8 or later.\n")
    sys.exit(2)

from own_asana.setup import main  # noqa: E402

sys.exit(main() or 0)
