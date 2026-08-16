"""Pin THIS repo's src ahead of any sibling editable install.

A sibling checkout pip-installed editable into the shared environment sorts
its .pth entry before ours, so bare `pytest` imported the sibling's
`autotrade` and 90 tests failed against foreign code. Tests must always run
against the tree they live in.
"""

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
while _SRC in sys.path:
    sys.path.remove(_SRC)
sys.path.insert(0, _SRC)
