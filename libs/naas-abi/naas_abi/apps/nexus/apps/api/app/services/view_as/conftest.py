"""The test world of ``view_as_http_test`` (the cast, their sessions, a migrated database,
the test IAM) for the other tests of the view that run over it."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.view_as.view_as_http_test import (  # noqa: F401
    migrated,
    world,
)
