"""Fixtures shared by the Nexus services' tests."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService


@pytest.fixture
def engine_iam():
    """The engine's IAM, in memory: what makes a link or a coding agent's key
    (``apps/links.py``, ``coding_environment/agent_credentials.py``) in a test
    that runs with no engine."""
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    previous = credentials.configure_iam(lambda: iam)
    yield iam
    credentials.configure_iam(previous)
