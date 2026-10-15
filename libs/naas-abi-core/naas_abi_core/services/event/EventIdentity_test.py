"""Every published event carries who triggered it, and in which workspace.

Identity comes from the call's ``CallContext``, set at the API boundary (or by
the NATS primary adapter), so no service that publishes events has to plumb
it through.
"""

from __future__ import annotations

import json
from typing import ClassVar

from naas_abi_core.engine.call_context import (
    ANONYMOUS,
    CallContext,
    current_call_context,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id
from naas_abi_core.services.event import EventCodec
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.context import (
    event_actor_user_id,
    event_actor_workspace_id,
    event_triggered_via,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess


class ObjectStored(LogProcess):
    _class_uri: ClassVar[str] = "http://example.org/ObjectStored"
    _property_uris: ClassVar[dict] = {"key": "http://example.org/key"}
    key: str | None = None


def _service(tmp_path) -> EventService:
    return EventService(adapter=EventSQLiteAdapter(str(tmp_path / "events.sqlite")))


def test_publish_stamps_actor_and_workspace_from_context(tmp_path) -> None:
    service = _service(tmp_path)
    tokens = (
        event_actor_user_id.set("usr-1"),
        event_actor_workspace_id.set("ws-1"),
        event_triggered_via.set("api"),
    )
    try:
        service.publish(ObjectStored(key="a.txt"))
    finally:
        event_actor_user_id.reset(tokens[0])
        event_actor_workspace_id.reset(tokens[1])
        event_triggered_via.reset(tokens[2])

    [stored] = service.query()
    assert (stored.actor_user_id, stored.actor_workspace_id, stored.triggered_via) == (
        "usr-1",
        "ws-1",
        "api",
    )


def test_publish_leaves_identity_empty_outside_a_request(tmp_path) -> None:
    service = _service(tmp_path)

    service.publish(ObjectStored(key="a.txt"))

    [stored] = service.query()
    assert stored.actor_user_id is None
    assert stored.actor_workspace_id is None
    assert stored.triggered_via is None


def test_caller_supplied_identity_wins_over_context(tmp_path) -> None:
    service = _service(tmp_path)
    token = event_actor_user_id.set("usr-context")
    try:
        service.publish(ObjectStored(key="a.txt", actor_user_id="usr-explicit"))
    finally:
        event_actor_user_id.reset(token)

    [stored] = service.query()
    assert stored.actor_user_id == "usr-explicit"


def test_the_actor_and_workspace_come_from_the_call_context(tmp_path) -> None:
    service = _service(tmp_path)
    caller = CallContext(
        principal=service_account("api"),
        on_behalf_of=user("usr-1"),
        workspace_id="ws-1",
        triggered_via="api",
    )
    with use_call_context(caller):
        assert event_actor_user_id.get() == "usr-1"
        assert event_actor_workspace_id.get() == "ws-1"
        assert event_triggered_via.get() == "api"
        service.publish(ObjectStored(key="a.txt"))
    # A service account acting for nobody is no user.
    with use_call_context(CallContext(principal=service_account("engine"))):
        service.publish(ObjectStored(key="b.txt"))

    first, second = service.query()
    assert (first.actor_user_id, first.actor_workspace_id, first.triggered_via) == (
        "usr-1",
        "ws-1",
        "api",
    )
    assert second.actor_user_id is None


def test_setting_the_actor_sets_whom_the_call_acts_for() -> None:
    with use_call_context(CallContext(principal=service_account("api"))):
        token = event_actor_user_id.set("usr-2")
        assert current_call_context().on_behalf_of == user("usr-2")
        assert current_call_context().principal == service_account("api")
        event_actor_user_id.reset(token)
        assert current_call_context().on_behalf_of is None


def test_a_user_actor_stays_the_calls_user_when_the_actor_is_cleared() -> None:
    with use_call_context(CallContext(principal=user("usr-actor"))):
        assert event_actor_user_id.get() == "usr-actor"
        token = event_actor_user_id.set("usr-other")
        assert event_actor_user_id.get() == "usr-other"
        cleared = event_actor_user_id.set(None)
        # Only on_behalf_of is cleared: the actor is a user, so it is the user.
        assert event_actor_user_id.get() == "usr-actor"
        event_actor_user_id.reset(cleared)
        event_actor_user_id.reset(token)
        assert current_call_context() == CallContext(principal=user("usr-actor"))


def test_a_reset_restores_its_field_only() -> None:
    user_token = event_actor_user_id.set("usr-1")
    event_actor_workspace_id.set("ws-1")
    event_actor_user_id.reset(user_token)
    # The workspace set after the user stays: a reset is not a ContextVar's.
    assert (event_actor_user_id.get(), event_actor_workspace_id.get()) == (None, "ws-1")
    event_actor_workspace_id.set(None)


def test_resets_in_any_order_restore_each_field() -> None:
    user_token = event_actor_user_id.set("usr-1")
    workspace_token = event_actor_workspace_id.set("ws-1")
    via_token = event_triggered_via.set("cli")

    event_actor_user_id.reset(user_token)
    assert (event_actor_workspace_id.get(), event_triggered_via.get()) == (
        "ws-1",
        "cli",
    )
    event_triggered_via.reset(via_token)
    event_actor_workspace_id.reset(workspace_token)

    assert current_call_context() == ANONYMOUS


def test_agent_context_vars_are_the_same_identity() -> None:
    """Chat sets agent_user_id / agent_workspace_id; events must see them."""
    assert agent_user_id is event_actor_user_id
    assert agent_workspace_id is event_actor_workspace_id


def test_payload_maps_inherited_identity_fields_to_iris() -> None:
    """Subclasses declare only their own _property_uris; the codec merges the MRO."""
    payload = json.loads(
        EventCodec.serialize(ObjectStored(key="a.txt", actor_user_id="usr-1"))
    )

    assert payload["actor_user_id"] == "usr-1"
    assert (
        payload["_property_uris"]["actor_user_id"]
        == "http://ontology.naas.ai/abi/actorUserId"
    )
    assert payload["_property_uris"]["key"] == "http://example.org/key"
