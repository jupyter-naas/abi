# mypy: disable-error-code="arg-type,misc"
from __future__ import annotations

import pytest

from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    ICodingEnvironmentAdapter,
    PHASE_PROVISIONING,
    PHASE_RUNNING,
    ProvisionTimeoutError,
    WorkspaceAccess,
    WorkspaceStatus,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from naas_abi_core.services.coding_environment.ontologies.modules.CodingEnvironmentEventOntology import (
    WorkspaceAccessGranted,
    WorkspaceDeleted,
    WorkspaceProvisioned,
    WorkspaceProvisionFailed,
    WorkspaceStarted,
    WorkspaceStopped,
)


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class _ExplodingEventService:
    def publish(self, event) -> None:
        raise RuntimeError("event bus down")


class _FakeServices:
    def __init__(self, events=None) -> None:
        self._events = events

    def events_available(self) -> bool:
        return self._events is not None

    @property
    def events(self):
        assert self._events is not None
        return self._events


class _BrokenAdapter(ICodingEnvironmentAdapter):
    def ensure_user(self, **kwargs) -> str:
        return "user-x"

    def list_templates(self):
        return []

    def provision(self, **kwargs) -> WorkspaceStatus:
        raise RuntimeError("provision boom")

    def start(self, **kwargs) -> WorkspaceStatus:
        raise RuntimeError("boom")

    def stop(self, **kwargs) -> WorkspaceStatus:
        raise RuntimeError("boom")

    def delete(self, **kwargs) -> None:
        raise RuntimeError("boom")

    def get_status(self, **kwargs) -> WorkspaceStatus:
        raise RuntimeError("boom")

    def get_access(self, **kwargs) -> WorkspaceAccess:
        raise RuntimeError("boom")


class _Clock:
    """Deterministic monotonic clock; advances by ``step`` each call."""

    def __init__(self, step: float = 1.0) -> None:
        self.t = 0.0
        self.step = step

    def monotonic(self) -> float:
        value = self.t
        self.t += self.step
        return value


def _wired_service(adapter, events=None) -> CodingEnvironmentService:
    svc = CodingEnvironmentService(adapter)
    svc.set_services(_FakeServices(events))
    return svc


def _provision(svc: CodingEnvironmentService) -> WorkspaceStatus:
    user_id = svc.ensure_user(
        external_id="ext-1", email="alice@example.com", username="alice"
    )
    return svc.provision(user_id=user_id, template_id="tmpl-default", name="dev")


def test_no_events_when_services_not_wired() -> None:
    svc = CodingEnvironmentService(InMemoryAdapter())
    status = _provision(svc)
    assert status.phase == PHASE_RUNNING


def test_no_events_when_events_unavailable() -> None:
    svc = _wired_service(InMemoryAdapter(), events=None)
    status = _provision(svc)
    assert status.phase == PHASE_RUNNING


def test_provision_emits_workspace_provisioned() -> None:
    events = _FakeEventService()
    svc = _wired_service(InMemoryAdapter(), events)

    status = _provision(svc)

    provisioned = [e for e in events.published if isinstance(e, WorkspaceProvisioned)]
    assert len(provisioned) == 1
    evt = provisioned[0]
    assert evt.workspace_id == status.id
    assert evt.workspace_name == "dev"
    assert evt.template_id == "tmpl-default"
    assert evt.phase == PHASE_RUNNING


def test_provision_failure_emits_failed_and_reraises() -> None:
    events = _FakeEventService()
    svc = _wired_service(_BrokenAdapter(), events)

    with pytest.raises(RuntimeError):
        svc.provision(user_id="user-x", template_id="tmpl", name="dev")

    failed = [e for e in events.published if isinstance(e, WorkspaceProvisionFailed)]
    assert len(failed) == 1
    assert "provision boom" in (failed[0].message or "")
    assert not any(isinstance(e, WorkspaceProvisioned) for e in events.published)


def test_publisher_exception_does_not_break_operation() -> None:
    svc = _wired_service(InMemoryAdapter(), events=_ExplodingEventService())
    # Must not raise even though every publish() throws.
    status = _provision(svc)
    assert status.phase == PHASE_RUNNING


def test_lifecycle_events_emitted() -> None:
    events = _FakeEventService()
    svc = _wired_service(InMemoryAdapter(), events)
    status = _provision(svc)

    svc.start(workspace_id=status.id)
    svc.stop(workspace_id=status.id)
    svc.delete(workspace_id=status.id)

    assert any(isinstance(e, WorkspaceStarted) for e in events.published)
    assert any(isinstance(e, WorkspaceStopped) for e in events.published)
    assert any(isinstance(e, WorkspaceDeleted) for e in events.published)


def test_get_access_emits_access_granted() -> None:
    events = _FakeEventService()
    svc = _wired_service(InMemoryAdapter(), events)
    status = _provision(svc)

    access = svc.get_access(
        workspace_id=status.id, user_id="user-1", app_slug="code-server"
    )

    assert "coder_session_token=" in access.url
    granted = [e for e in events.published if isinstance(e, WorkspaceAccessGranted)]
    assert len(granted) == 1
    assert granted[0].app_slug == "code-server"


def test_wait_until_ready_returns_when_agent_ready() -> None:
    # Workspace needs two get_status polls before it reports ready.
    svc = CodingEnvironmentService(InMemoryAdapter(polls_until_ready=2))
    status = svc.provision(user_id="user-1", template_id="t", name="dev")
    assert status.phase == PHASE_PROVISIONING

    clock = _Clock(step=1.0)
    ready = svc.wait_until_ready(
        workspace_id=status.id,
        timeout_seconds=300.0,
        poll_interval_seconds=0.0,
        sleep=lambda _s: None,
        monotonic=clock.monotonic,
    )
    assert ready.phase == PHASE_RUNNING
    assert ready.agent_ready is True


def test_wait_until_ready_times_out() -> None:
    # Never becomes ready within the deadline.
    svc = CodingEnvironmentService(InMemoryAdapter(polls_until_ready=10_000))
    status = svc.provision(user_id="user-1", template_id="t", name="dev")

    clock = _Clock(step=1.0)
    with pytest.raises(ProvisionTimeoutError):
        svc.wait_until_ready(
            workspace_id=status.id,
            timeout_seconds=2.0,
            poll_interval_seconds=0.0,
            sleep=lambda _s: None,
            monotonic=clock.monotonic,
        )
