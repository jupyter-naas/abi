from __future__ import annotations

import pytest

from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    PHASE_RUNNING,
    PHASE_STOPPED,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
)
from naas_abi_core.services.coding_environment.tests.coding_environment__secondary_adapter__generic_test import (
    GenericCodingEnvironmentSecondaryAdapterTest,
)


class TestInMemoryAdapter(GenericCodingEnvironmentSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return InMemoryAdapter


def test_ensure_user_is_idempotent() -> None:
    adapter = InMemoryAdapter()
    a = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    b = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    assert a == b


def test_full_lifecycle() -> None:
    adapter = InMemoryAdapter()
    user_id = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")

    status = adapter.provision(user_id=user_id, template_id="tmpl-default", name="dev")
    assert status.phase == PHASE_RUNNING
    assert status.agent_ready is True

    stopped = adapter.stop(workspace_id=status.id)
    assert stopped.phase == PHASE_STOPPED
    assert stopped.agent_ready is False

    started = adapter.start(workspace_id=status.id)
    assert started.phase == PHASE_RUNNING

    adapter.delete(workspace_id=status.id)
    with pytest.raises(WorkspaceNotFoundError):
        adapter.get_status(workspace_id=status.id)


def test_duplicate_name_raises_conflict() -> None:
    adapter = InMemoryAdapter()
    user_id = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    adapter.provision(user_id=user_id, template_id="t", name="dev")
    with pytest.raises(WorkspaceNameConflictError):
        adapter.provision(user_id=user_id, template_id="t", name="dev")


def test_provision_becomes_ready_after_polls() -> None:
    adapter = InMemoryAdapter(polls_until_ready=2)
    user_id = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    status = adapter.provision(user_id=user_id, template_id="t", name="dev")
    assert status.agent_ready is False

    adapter.get_status(workspace_id=status.id)  # poll 1
    second = adapter.get_status(workspace_id=status.id)  # poll 2 -> ready
    assert second.phase == PHASE_RUNNING
    assert second.agent_ready is True


def test_get_access_returns_embeddable_url_with_token() -> None:
    adapter = InMemoryAdapter()
    user_id = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    status = adapter.provision(user_id=user_id, template_id="t", name="dev")

    access = adapter.get_access(
        workspace_id=status.id, user_id=user_id, app_slug="code-server"
    )
    assert access.token is not None
    assert access.token in access.url
    assert access.url.startswith("https://code-server--main--dev--")
