"""Every published event carries who triggered it, and in which workspace.

Identity comes from request-scoped ContextVars set at the API boundary, so no
service that publishes events has to plumb it through.
"""

from __future__ import annotations

import json
from typing import ClassVar

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
