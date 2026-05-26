"""Analytics endpoint shim.

The full implementation lives in
``naas_abi.apps.nexus.apps.api.app.services.analytics`` (hexagonal layout:
port, service, primary/secondary adapters, handler). This module simply
re-exports the FastAPI router so ``api/router.py`` can keep importing
analytics from ``endpoints`` alongside the other endpoint modules.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.analytics.handlers import router

__all__ = ["router"]
