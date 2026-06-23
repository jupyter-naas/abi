from __future__ import annotations

import pytest

from naas_abi_core.services.coding_environment.adapters.secondary.CodeServerComposeAdapter import (
    CodeServerComposeAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    PHASE_RUNNING,
)
from naas_abi_core.services.coding_environment.tests.coding_environment__secondary_adapter__generic_test import (
    GenericCodingEnvironmentSecondaryAdapterTest,
)


class TestCodeServerComposeAdapter(GenericCodingEnvironmentSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return CodeServerComposeAdapter


def test_provision_reports_running() -> None:
    adapter = CodeServerComposeAdapter(url="https://code-server.example.com")
    status = adapter.provision(user_id="u", template_id="t", name="dev")
    assert status.phase == PHASE_RUNNING
    assert status.agent_ready is True


def test_get_access_returns_configured_url_without_token() -> None:
    adapter = CodeServerComposeAdapter(url="https://code-server.example.com")
    access = adapter.get_access(
        workspace_id="code-server", user_id="u", app_slug="code-server"
    )
    assert access.url == "https://code-server.example.com/"
    assert access.token is None  # same-site => first-party cookie, no token passthrough


def test_url_trailing_slash_normalized() -> None:
    adapter = CodeServerComposeAdapter(url="https://x.example.com/")
    access = adapter.get_access(workspace_id="w", user_id="u", app_slug="s")
    assert access.url == "https://x.example.com/"


def test_ensure_user_echoes_external_id() -> None:
    adapter = CodeServerComposeAdapter(url="https://x.example.com")
    assert (
        adapter.ensure_user(external_id="ext-1", email="a@b.c", username="alice")
        == "ext-1"
    )


def test_lifecycle_is_noop_but_reports_running() -> None:
    adapter = CodeServerComposeAdapter(url="https://x.example.com")
    assert adapter.start(workspace_id="w").phase == PHASE_RUNNING
    assert adapter.stop(workspace_id="w").phase == PHASE_RUNNING
    adapter.delete(workspace_id="w")  # no-op; returns None
    assert adapter.get_status(workspace_id="w").phase == PHASE_RUNNING
