"""The WSR API runs from its own directory (``uvicorn main:app``): its modules
are top-level there."""

import sys
from pathlib import Path

API = str(Path(__file__).resolve().parents[1])
if API not in sys.path:
    sys.path.insert(0, API)
