"""HTTP handler that wires the analytics domain + adapters + router.

Module-level wiring is deliberate: the Nexus API includes this router
at startup (see :mod:`app.api.router`). The TTL files are resolved
from environment variables with a sensible default that points at the
checked-in fake-data file in ``ontologies/sandbox``.
"""

from __future__ import annotations

import os
from pathlib import Path

from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.primary import (
    build_router,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__SPARQL import (
    SPARQLAnalyticsAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.service import AnalyticsService

_NAAS_ABI_ROOT = Path(__file__).resolve().parents[8]
# Path layout:
#   .../naas_abi/apps/nexus/apps/api/app/services/analytics/handlers/<this>
#       ^8     ^7   ^6    ^5  ^4 ^3 ^2       ^1        ^0
# → libs/naas-abi/naas_abi/

DEFAULT_TTL_PATHS = [
    _NAAS_ABI_ROOT / "ontologies" / "modules" / "NexusPlatformOntology.ttl",
    _NAAS_ABI_ROOT / "ontologies" / "sandbox" / "NexusAnalyticsData.ttl",
]


def _resolved_ttl_paths() -> list[Path]:
    env = os.environ.get("ANALYTICS_TTL_PATHS")
    if env:
        return [Path(p).expanduser().resolve() for p in env.split(os.pathsep) if p]
    return DEFAULT_TTL_PATHS


def _build_service() -> AnalyticsService:
    adapter = SPARQLAnalyticsAdapter(_resolved_ttl_paths())
    return AnalyticsService(adapter=adapter)


service = _build_service()
router = build_router(service)
