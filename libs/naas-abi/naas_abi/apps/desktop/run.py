"""Standalone launcher for ABI Desktop.

Imports the app as the top-level ``desktop`` package (adding the parent
``apps`` directory to ``sys.path``) so that ``naas_abi/__init__.py`` — which
pulls in the full engine, marketplace, and Nexus stack — is never imported.
This is what keeps the compiled executable small.

Usage:
    uv run python libs/naas-abi/naas_abi/apps/desktop/run.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from desktop.main import main  # type: ignore[import-not-found]  # noqa: E402

if __name__ == "__main__":
    main()
