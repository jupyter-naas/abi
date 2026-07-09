"""Pytest bootstrap for ABI Desktop tests.

Mirrors ``run.py``: the app must import as the top-level ``desktop`` package
(never as ``naas_abi.apps.desktop``) so the heavy ``naas_abi`` engine is
never loaded. Inserting the parent ``apps`` directory into ``sys.path``
makes ``import desktop.*`` deterministic regardless of pytest import mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = str(Path(__file__).resolve().parent.parent)
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)
