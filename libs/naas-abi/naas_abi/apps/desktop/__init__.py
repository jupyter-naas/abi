"""ABI Desktop package.

Ensures ``import desktop.*`` works when uvicorn reload subprocesses import
modules directly (without ``run.py`` on ``sys.path``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = str(Path(__file__).resolve().parent.parent)
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)
