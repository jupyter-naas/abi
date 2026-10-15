"""The event log authorizes every operation, in process and over NATS alike
(RFC §6.4 "event")."""

from __future__ import annotations

from typing import ClassVar

import pytest

from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.event.adapters.primary.event__primary_adapter__NATS import (
    EventPrimaryAdapterNATS,
)
from naas_abi_core.services.event.adapters.secondary.EventSecondaryAdapterNATSClient import (
    EventSecondaryAdapterNATSClient,
)
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.EventPort import EventNotFoundError, StoredEvent
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.iam.names import resource_name
from naas_abi_core.services.iam.tests.authorization_contract import (
    JWT_SECRET,
    AuthorizationContract,
    contract_iam,
    wire,
)
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement


class Opened(LogProcess):
    _class_uri: ClassVar[str] = "http://example.org/Opened"


class Closed(LogProcess):
    _class_uri: ClassVar[str] = "http://example.org/Closed"


def event_type(cls: type[LogProcess]) -> str:
    return resource_name("event", "event_type", str(cls._class_uri))


def cursor(consumer: str, cls: type[LogProcess]) -> str:
    return resource_name(
        "event", "cursor", (consumer, str(cls._class_uri)), kind="path"
    )


class EventContract(AuthorizationContract):
    NOT_FOUND = (EventNotFoundError,)

    @pytest.fixture
    def owner(self, contract_iam, tmp_path):
        return wire(
            EventService(EventSQLiteAdapter(str(tmp_path / "e.db"))), contract_iam
        )

    def primary(self, owner):
        return EventPrimaryAdapterNATS(owner, JWT_SECRET)

    def facade(self, nats_url, identity):
        return EventService(
            EventSecondaryAdapterNATSClient(nats_url, TEST_TOKENS.source(identity))
        )


class TestAppend(EventContract):
    ACTION = "event:Append"

    def resource(self, owner):
        return event_type(Opened)

    def call(self, service):
        return service.publish(Opened())


class TestQuery(EventContract):
    ACTION = "event:Query"

    def prepare(self, owner):
        owner.publish(Opened())

    def resource(self, owner):
        return event_type(Opened)

    def call(self, service):
        assert len(service.query(Opened)) == 1


class TestQueryStream(EventContract):
    """Over NATS the client pins the stream's snapshot with max_seq first,
    so a remote streamed read also needs MaxSeq (every role grants both)."""

    ACTION = "event:QueryStream"

    def prepare(self, owner):
        owner.publish(Opened())

    def resource(self, owner):
        return event_type(Opened)

    def call(self, service):
        with service.query_stream(Opened) as stream:
            assert len(list(stream)) == 1

    def _grant(self, h, caller, *statements):
        h.grant(
            caller.id,
            *statements,
            statement("Allow", ["event:MaxSeq"], [event_type(Opened)]),
        )


class TestGetCursor(EventContract):
    ACTION = "event:GetCursor"

    def resource(self, owner):
        return cursor("worker", Opened)

    def call(self, service):
        return service.get_cursor("worker", str(Opened._class_uri))


# -- in process -----------------------------------------------------------------------


@pytest.fixture
def h():
    return IAMHarness(contract_iam())


@pytest.fixture
def events(h, tmp_path):
    service = wire(EventService(EventSQLiteAdapter(str(tmp_path / "e.db"))), h.iam)
    with as_service_account("engine"):
        service.publish(Opened())
        service.publish(Closed())
        service.publish(Opened())
    return service


@pytest.fixture
def bob(h):
    """An IAM user who may read ``Opened`` only."""
    bob = h.user()
    h.grant(
        bob.id,
        statement(
            "Allow",
            [
                "event:Query",
                "event:QueryStream",
                "event:MaxSeq",
                "event:ListEventTypes",
            ],
            [event_type(Opened)],
        ),
    )
    return bob


def test_a_query_with_no_type_returns_only_the_readable_types(h, events, bob):
    with h.as_(actor="api", on_behalf_of=bob):
        rows = events.query_stored()
        assert {r.event_type for r in rows} == {str(Opened._class_uri)}
        assert [r.seq for r in events.query_stored(limit=1, newest_first=True)] == [3]
        assert len(events.query()) == 2
        with events.query_stored_stream(limit=1) as stream:
            assert [r.seq for r in stream] == [1]
    with as_service_account("engine"):
        assert len(events.query_stored()) == 3


def test_iter_query_with_no_type_is_filtered(h, events, bob):
    with h.as_(actor="api", on_behalf_of=bob):
        assert [e._seq for e in events.iter_query(batch_size=1)] == [1, 3]


def test_event_types_and_max_seq_reveal_only_the_readable_types(h, events, bob):
    with h.as_(actor="api", on_behalf_of=bob):
        assert [s.event_type for s in events.event_types()] == [str(Opened._class_uri)]
        assert events.max_seq() == 3
        with pytest.raises(EventNotFoundError):
            events.max_seq(str(Closed._class_uri))
    nobody = h.user("nobody")
    with h.as_(actor="api", on_behalf_of=nobody):
        assert events.event_types() == []
        assert events.max_seq() == 0
        assert events.query_stored() == []


def test_a_row_of_an_unreadable_type_is_not_found(h, events, bob):
    with h.as_(actor="api", on_behalf_of=bob):
        assert events.get_stored(1).seq == 1
        with pytest.raises(EventNotFoundError, match="No event with seq 2"):
            events.get_stored(2)


def test_consumer_reads_need_the_type_and_the_cursor(h, events):
    carol = h.user("carol")
    h.grant(
        carol.id,
        statement("Allow", ["event:QueryForConsumer"], [event_type(Opened)]),
    )
    with h.as_(actor="api", on_behalf_of=carol), pytest.raises(EventNotFoundError):
        events.query_for_consumer("worker", Opened)
    h.grant(
        carol.id,
        statement("Allow", ["event:QueryForConsumer"], [cursor("worker", Opened)]),
    )
    with h.as_(actor="api", on_behalf_of=carol):
        assert len(events.query_for_consumer("worker", Opened)) == 2
        with pytest.raises(EventNotFoundError):
            events.query_for_consumer("worker", Closed)


def test_subscribing_needs_query_on_the_type(h, events, bob):
    from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
        PythonQueueAdapter,
    )
    from naas_abi_core.services.bus.BusService import BusService

    events._explicit_bus = BusService(PythonQueueAdapter())
    with h.as_(actor="api", on_behalf_of=bob):
        events.subscribe(Opened, lambda event: None)
        with pytest.raises(EventNotFoundError):
            events.subscribe(Closed, lambda event: None)


# -- emit -----------------------------------------------------------------------------


def test_emit_appends_as_the_engine_stamped_with_the_callers_user(h, events, bob):
    """A kernel service's audit event: Bob may not Append ``Closed``."""
    with h.as_(actor="api", on_behalf_of=bob):
        with pytest.raises(PermissionDeniedError):
            events.publish(Opened())
        stored = events.emit(Closed())
    assert isinstance(stored, StoredEvent)
    with as_service_account("engine"):
        (event,) = events.query(Closed, newest_first=True, limit=1)
    assert event.actor_user_id == bob.id


def test_emit_never_raises(tmp_path):
    class Failing(EventSQLiteAdapter):
        def append(self, *args, **kwargs):
            raise RuntimeError("log down")

    events = EventService(Failing(str(tmp_path / "e.db")))
    with use_call_context(
        CallContext(principal=Principal(id="api", kind="service_account", name="api"))
    ):
        assert events.emit(Opened()) is None
