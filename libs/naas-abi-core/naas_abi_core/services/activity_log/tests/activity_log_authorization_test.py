"""The activity log authorizes every operation, in process and over NATS alike
(RFC §6.4 "activity_log"); a recorded event's actor is the call's."""

from __future__ import annotations

import pytest
from naas_abi_core.engine.call_context import (
    ANONYMOUS,
    CallContext,
    as_service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.activity_log.adapters.primary.activity_log__primary_adapter__NATS import (
    ActivityLogPrimaryAdapterNATS,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSecondaryAdapterNATSClient import (
    ActivityLogSecondaryAdapterNATSClient,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
    ActivityLogSqliteAdapter,
)
from naas_abi_core.services.iam.IAMPorts import ResourceNotFoundError
from naas_abi_core.services.iam.tests.authorization_contract import (
    JWT_SECRET,
    AuthorizationContract,
    contract_iam,
    wire,
)
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement

ACTOR = "someone"


def actor(actor_id: str) -> str:
    return f"abi:-:-:activity_log:actor/{actor_id}"


class ActivityLogContract(AuthorizationContract):
    @pytest.fixture
    def owner(self, contract_iam, tmp_path):
        return wire(
            ActivityLogService(ActivityLogSqliteAdapter(str(tmp_path))), contract_iam
        )

    def primary(self, owner):
        return ActivityLogPrimaryAdapterNATS(owner, JWT_SECRET)

    def facade(self, nats_url, identity):
        return ActivityLogService(
            ActivityLogSecondaryAdapterNATSClient(
                nats_url, TEST_TOKENS.source(identity)
            )
        )

    def close_facade(self, facade):
        facade.adapter.close()

    def prepare(self, owner):
        with use_call_context(CallContext(principal=user(ACTOR))):
            owner.record(ActivityEvent(actor_id="ignored", event_type="x"))

    def resource(self, owner):
        return actor(ACTOR)


class TestQuery(ActivityLogContract):
    ACTION = "activity_log:Query"

    def call(self, service):
        assert len(service.query(ACTOR)) == 1


class TestQueryStream(ActivityLogContract):
    """Over NATS the client pins the stream's snapshot with ``query`` first, so
    a remote streamed read also needs Query (``builtin.self`` grants both)."""

    ACTION = "activity_log:QueryStream"

    def call(self, service):
        with service.query_stream(ACTOR) as events:
            assert len(list(events)) == 1

    def _grant(self, h, caller, *statements):
        h.grant(
            caller.id,
            *statements,
            statement("Allow", ["activity_log:Query"], [actor(ACTOR)]),
        )


# -- in process -----------------------------------------------------------------------


@pytest.fixture
def h():
    return IAMHarness(contract_iam())


@pytest.fixture
def log(h, tmp_path):
    return wire(ActivityLogService(ActivityLogSqliteAdapter(str(tmp_path))), h.iam)


def test_the_actor_is_the_calls_user_never_the_events_field(h, log):
    bob = h.user()
    with h.as_(actor="api", on_behalf_of=bob):
        log.record(ActivityEvent(actor_id="alice", event_type="http.request"))
    with as_service_account("engine"):
        assert log.list_actors() == [bob.id]
        assert log.query("alice") == []


def test_a_service_account_records_under_its_own_name(h, log):
    with as_service_account("api"):
        log.record(ActivityEvent(actor_id="anonymous", event_type="http.request"))
    with as_service_account("engine"):
        assert log.list_actors() == ["api"]


def test_an_anonymous_call_records_nothing(h, log):
    with use_call_context(ANONYMOUS):
        log.record(ActivityEvent(actor_id="alice", event_type="x"))
    with as_service_account("engine"):
        assert log.list_actors() == []


def test_a_denied_record_is_dropped_without_breaking_the_caller(h, log):
    """A recorded service account with no policy may not record."""
    h.service_account("quiet")
    with h.as_(actor="quiet"):
        log.record(ActivityEvent(actor_id="quiet", event_type="x"))
    with as_service_account("engine"):
        assert log.list_actors() == []


def test_a_user_reads_their_own_log_and_no_one_elses(h, log):
    bob, carol = h.user("bob"), h.user("carol")
    for who in (bob, carol):
        with h.as_(actor="api", on_behalf_of=who):
            log.record(ActivityEvent(actor_id="x", event_type="x"))
    with h.as_(actor="api", on_behalf_of=bob):
        assert [e.actor_id for e in log.query(bob.id)] == [bob.id]
        with log.query_stream(bob.id) as events:
            assert len(list(events)) == 1
        with pytest.raises(ResourceNotFoundError):
            log.query(carol.id)


def test_list_actors_returns_only_the_actors_the_caller_may_list(h, log):
    bob, carol = h.user("bob"), h.user("carol")
    for who in (bob, carol):
        with h.as_(actor="api", on_behalf_of=who):
            log.record(ActivityEvent(actor_id="x", event_type="x"))
    admin = h.user("admin")
    h.grant(
        admin.id, statement("Allow", ["activity_log:ListActors"], [actor(carol.id)])
    )
    with h.as_(actor="api", on_behalf_of=admin):
        assert log.list_actors() == [carol.id]
    with h.as_(actor="api", on_behalf_of=bob):
        assert log.list_actors() == []


def test_shutdown_is_an_admin_action(h, log):
    bob = h.user()
    with h.as_(actor="api", on_behalf_of=bob), pytest.raises(ResourceNotFoundError):
        log.shutdown()
