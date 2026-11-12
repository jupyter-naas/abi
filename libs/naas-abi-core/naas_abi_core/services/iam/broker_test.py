import pytest

from naas_abi_core.services.iam import broker
from naas_abi_core.services.iam.adapters import iam_nats_codec
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import Bound, EffectiveStatement
from naas_abi_core.services.iam.kernel_catalogs import kernel_catalogs
from naas_abi_core.services.iam.policy import Statement

ACCOUNT = "sa_01jabcdefghjkmnpqrstvwxyz0"
SA = "01jabcdefghjkmnpqrstvwxyz0"
KEY = "abcdefghijklmnop"


def derive(*statements: Statement, module=("acme", "people"), catalogs=None):
    return broker.derive(
        principal_id=ACCOUNT,
        key_id=KEY,
        statements=[EffectiveStatement(s, "p", i) for i, s in enumerate(statements)],
        catalogs=catalogs or CatalogRegistry(),
        module=module,
    )


def kernel() -> CatalogRegistry:
    registry = CatalogRegistry()
    for catalog in kernel_catalogs():
        registry.register(catalog)
    return registry


def allow(actions, resources=("*",)):
    return Statement("Allow", tuple(actions), tuple(resources))


def js_api(permissions):
    return [s for s in permissions.publish if s.startswith("$JS.")]


def test_nothing_granted_reaches_iam_requests_its_inbox_and_its_hosting_only():
    permissions = derive()
    assert "abi.iam.v1.token" in permissions.publish
    assert "abi.iam.v1.submit_manifest" in permissions.publish
    # Replies and stream inboxes only: never a connection's own inboxes.
    assert "_INBOX.>" not in permissions.publish
    assert set(broker.REPLY_INBOXES) | set(broker.STREAM_INBOXES) <= set(
        permissions.publish
    )
    assert "abi.rpc.overflow.>" in permissions.publish
    assert js_api(permissions) == []
    assert permissions.subscribe == (
        f"_INBOX.{KEY}.m.>",
        f"abi.agent.acme.{SA}.>",
        f"abi.mod.acme.{SA}.>",
    )


def test_iam_change_notices_are_never_publishable():
    # Anyone publishing abi.iam.v1.changed would drop every engine's IAM cache.
    for permissions in (derive(), derive(allow(["*"]))):
        assert iam_nats_codec.CHANGED_SUBJECT not in permissions.publish
        assert not any(
            s.startswith("abi.iam.") and s.endswith((">", "*"))
            for s in permissions.publish
        )


def test_iam_request_subjects_are_the_codecs_operations():
    assert set(broker.IAM_OPERATIONS) == set(iam_nats_codec.OPERATIONS)


def test_a_concrete_discovery_action_reaches_discovery_only():
    permissions = derive(allow(["discovery:Register"]))
    assert "abi.discovery.acme.v1.>" in permissions.publish
    assert not any(
        s.startswith(("abi.agent.", "abi.mod.", "abi.jobs."))
        for s in permissions.publish
    )


def test_invoking_agents_reaches_their_subjects_in_the_project():
    permissions = derive(allow(["discovery:InvokeAgent", "discovery:ChatModel"]))
    assert "abi.agent.acme.*.*.*.v1.*" in permissions.publish
    assert "abi.mod.acme.*.*.model.*.chat" in permissions.publish
    assert "abi.mod.acme.*.*.app.*.http" not in permissions.publish


def test_another_account_reaches_the_projects_its_resources_name():
    permissions = derive(
        allow(["discovery:InvokeAgent"], ["abi:discovery:agent/beta/research/*"]),
        module=None,
    )
    assert "abi.discovery.beta.v1.>" in permissions.publish
    assert "abi.agent.beta.*.*.*.v1.*" in permissions.publish
    anywhere = derive(allow(["discovery:InvokeAgent"]), module=None)
    assert "abi.discovery.*.v1.>" in anywhere.publish


def test_a_pattern_of_another_service_opens_no_discovery_subject():
    """``abi:keyvalue:*`` (and its every-container form) names keyvalue only: a
    discovery action granted on it opens no discovery, agent or module subject.
    Only a wildcard where the service is written reaches every service."""

    def discovery_subjects(*resources):
        permissions = derive(allow(["discovery:*"], resources), module=None)
        return [
            s
            for s in permissions.publish
            if s.startswith(("abi.discovery.", "abi.agent.", "abi.mod."))
        ]

    assert discovery_subjects("abi:keyvalue:*", "abi:*/keyvalue:*") == []
    assert discovery_subjects("abi:keyvalue:key/x") == []
    for reaching in ("*", "abi:*", "abi:*:agent/*", "abi:disc*:*"):
        assert "abi.discovery.*.v1.>" in discovery_subjects(reaching), reaching
    assert "abi.discovery.beta.v1.>" in discovery_subjects(
        "abi:*/discovery:agent/beta/*"
    )


def test_a_service_wildcard_reaches_the_service_not_every_live_subject():
    permissions = derive(allow(["event:*"]))
    assert "abi.svc.event.v1.>" in permissions.publish
    assert not any(s.startswith("evt.") for s in permissions.subscribe)
    assert not any(s.startswith("evt.") for s in permissions.publish)


def test_a_catalogued_action_reaches_every_subject_its_endpoint_serves():
    """Catalog subjects are all a module gets: an action reaches its call, its
    variants and the transfer session a large call goes through."""
    permissions = derive(
        allow(["model_registry:Chat", "source_control:EnsureRepo"]),
        catalogs=kernel(),
    )
    for subject in (
        "abi.svc.model_registry.v1.chat",
        "abi.svc.model_registry.v1.transfer.open",
        "abi.svc.model_registry.v1.transfer.c0c0.write",
        "abi.svc.source_control.v1.ensure_repo",
        "abi.svc.source_control.v1.create_repo",
    ):
        assert any(broker.subject_matches(p, subject) for p in permissions.publish), (
            subject
        )
    assert "abi.svc.model_registry.v1.>" not in permissions.publish
    assert "abi.svc.source_control.v1.delete_repo" not in permissions.publish


def test_identity_is_reached_on_its_own_subjects():
    permissions = derive(
        allow(["identity:ListProviders", "identity:GetProvider"]), catalogs=kernel()
    )
    assert "abi.identity.v1.list_providers" in permissions.publish
    assert "abi.identity.v1.get_provider" in permissions.publish
    assert not any(p.startswith("abi.identity.v1.auth") for p in permissions.publish)
    # Without a registered catalog, the whole identity prefix.
    assert "abi.identity.v1.>" in derive(allow(["identity:*"])).publish


def test_a_deny_on_everything_takes_the_service_back():
    permissions = derive(
        allow(["keyvalue:*"]), Statement("Deny", ("keyvalue:*",), ("*",))
    )
    assert "abi.svc.keyvalue.v1.>" not in permissions.publish


# -- bus ------------------------------------------------------------------------------


def _consumes(permissions, topic):
    stream = broker.bus_stream(topic)
    return (
        f"$JS.API.CONSUMER.MSG.NEXT.{stream}.>" in permissions.publish
        or f"$JS.ACK.{stream}.>" in permissions.publish
    )


def test_publishing_a_topic_neither_subscribes_nor_fetches():
    topic = "demo.inbox"
    permissions = derive(allow(["bus:Publish"], [f"abi:bus:topic/{topic}"]))
    assert topic in permissions.publish and f"{topic}.>" in permissions.publish
    assert broker.topic_claim_subjects(topic) in permissions.publish  # claim checks
    assert not any(s.startswith(topic) for s in permissions.subscribe)
    assert not _consumes(permissions, topic)
    assert permissions.bus_publish == (topic,) and permissions.bus_consume == ()


def test_consuming_a_topic_neither_publishes_nor_writes_claim_checks():
    topic = "demo.inbox"
    permissions = derive(allow(["bus:Consume"], [f"abi:bus:topic/{topic}"]))
    assert topic in permissions.subscribe and f"{topic}.>" in permissions.subscribe
    assert _consumes(permissions, topic)
    assert topic not in permissions.publish
    assert f"{topic}.>" not in permissions.publish
    assert broker.topic_claim_subjects(topic) not in permissions.publish
    assert permissions.bus_publish == () and permissions.bus_consume == (topic,)


def test_an_unknown_bus_action_reaches_nothing():
    permissions = derive(allow(["bus:Admin"], ["abi:bus:topic/demo.inbox"]))
    assert permissions.bus_topics == ()
    assert "demo.inbox" not in permissions.publish + permissions.subscribe


def test_a_deny_on_one_topic_keeps_it_from_that_action_only():
    permissions = derive(
        allow(["bus:*"], ["abi:bus:topic/a", "abi:bus:topic/b"]),
        Statement("Deny", ("bus:Consume",), ("abi:bus:topic/b",)),
    )
    assert permissions.bus_consume == ("a",)
    assert set(permissions.bus_publish) == {"a", "b"}  # still publishes on b
    assert _consumes(permissions, "a") and not _consumes(permissions, "b")
    assert "b.>" not in permissions.subscribe
    assert "b.>" in permissions.publish


EVERYWHERE = "abi:*/event:event_type/"
OWN_TYPE = "https://example.org/ontology#OwnEvent"
OTHER_TYPE = "https://example.org/ontology#OtherEvent"


def _type(event_type: str, prefix: str = EVERYWHERE) -> str:
    from urllib.parse import quote

    return prefix + quote(event_type, safe="")


PLATFORM = "abi:event:event_type/"


def _everywhere(event_type: str) -> list[str]:
    return [_type(event_type, PLATFORM), _type(event_type)]


def test_live_events_keep_to_the_types_a_statement_reads_everywhere():
    registry = kernel()
    own = broker.live_event_subjects(OWN_TYPE)
    reads = derive(allow(["event:Query"], _everywhere(OWN_TYPE)), catalogs=registry)
    assert set(own) <= set(reads.subscribe)
    assert broker.live_event_subject(OTHER_TYPE) not in reads.subscribe
    assert "evt.>" not in reads.subscribe
    # A live subject carries the type's events at the platform and in every
    # container: a grant on fewer names reads it through the service only.
    for narrower in (
        [_type(OWN_TYPE)],  # every container, not the platform's
        [_type(OWN_TYPE, PLATFORM)],  # the platform's only
        [_type(OWN_TYPE, "abi:nexus:organization/o-1/event:event_type/")],
        ["abi:*/event:event_type/*"],
        ["*"],
    ):
        permissions = derive(allow(["event:Query"], narrower), catalogs=registry)
        assert not any(s.startswith("evt.") for s in permissions.subscribe), narrower
    # Listing types or cursors reads no live subject.
    for action in ("ListEventTypes", "GetCursor", "SetCursor", "MaxSeq"):
        listed = derive(
            allow([f"event:{action}"], _everywhere(OWN_TYPE)), catalogs=registry
        )
        assert not any(s.startswith("evt.") for s in listed.subscribe), action


def test_live_events_keep_to_what_no_deny_bound_or_scope_narrows():
    registry = kernel()
    everywhere = allow(["event:*"], _everywhere(OWN_TYPE))
    for deny in (
        # One container's events of the type, or another type's: the live
        # subject would carry them, so neither leaves it granted.
        Statement(
            "Deny",
            ("event:Query", "event:QueryStream", "event:QueryForConsumer"),
            (_type(OWN_TYPE, "abi:nexus:organization/o-1/event:event_type/"),),
        ),
        Statement("Deny", ("event:*",), (_type(OWN_TYPE, PLATFORM),)),
        Statement("Deny", ("event:*",), ("abi:*/event:event_type/*",)),
    ):
        permissions = derive(everywhere, deny, catalogs=registry)
        assert not any(s.startswith("evt.") for s in permissions.subscribe), deny
    # A statement bounded by a parent chain, or attached at a scope, leaves some
    # names out: it grants no live subject.
    bounded = EffectiveStatement(everywhere, "p", 0, bounds=(Bound("parent", ()),))
    scoped = EffectiveStatement(everywhere, "p", 0, scope="abi:nexus:organization/o-1")
    for effective in (bounded, scoped):
        permissions = broker.derive(
            principal_id=ACCOUNT,
            key_id=KEY,
            statements=[effective],
            catalogs=registry,
            module=("acme", "people"),
        )
        assert not any(s.startswith("evt.") for s in permissions.subscribe)
    # A type is read as the service spells it: a non-canonical spelling of the
    # same type names nothing the service matches.
    from urllib.parse import quote

    canonical = quote(OWN_TYPE, safe="")
    odd = canonical.replace("%3A", "%3a").replace("e", "%65", 1)
    spelled = derive(
        allow(["event:Query"], [PLATFORM + odd, "abi:*/event:event_type/" + odd]),
        catalogs=registry,
    )
    assert not any(s.startswith("evt.") for s in spelled.subscribe)


def test_live_events_are_never_published_by_a_module():
    registry = kernel()
    for statement in (
        allow(["event:Append"], [_type(OWN_TYPE)]),
        allow(["event:*"], [_type(OWN_TYPE)]),
        allow(["event:*"]),
        allow(["*"]),
    ):
        permissions = derive(statement, catalogs=registry)
        assert not any(s.startswith("evt") for s in permissions.publish)


def test_live_event_subject_keeps_in_step_with_the_event_service():
    from naas_abi_core.services.event.EventService import class_iri_to_topic

    assert broker.live_event_subject(OWN_TYPE) == class_iri_to_topic(OWN_TYPE)


def test_inbox_publishing_keeps_to_replies_and_streams():
    """A module answers the reply subject of a request, and pushes to a stream
    inbox it was handed: never another connection's own inboxes, which anyone
    who saw one of its reply subjects predicts."""
    from naas_abi_sdk import messages

    assert broker.MODULE_INBOX_TOKEN == messages.MODULE_INBOX_TOKEN
    assert broker.STREAM_TOKEN == messages.STREAM_TOKEN
    publish = derive().publish
    secret = "a" * 32
    allowed = (
        "_INBOX.AbCd1234.AbCd5678ef",  # an engine connection's request reply
        f"_INBOX.{KEY}.m.AbCd1234.AbCd5678ef",  # a module's request reply
        f"_INBOX.AbCd1234.stream.{secret}",
        f"_INBOX.{KEY}.m.AbCd1234.stream.{secret}",
    )
    refused = (
        "_INBOX.AbCd1234",  # an engine connection's own inbox
        f"_INBOX.{KEY}.m.AbCd1234",  # a module connection's own inbox
        "_INBOX.a.b.c.d.e.f",
    )
    for subject in allowed:
        assert any(broker.subject_matches(p, subject) for p in publish), subject
    for subject in refused:
        assert not any(broker.subject_matches(p, subject) for p in publish), subject
    assert messages.is_stream_inbox(allowed[2]) and messages.is_stream_inbox(allowed[3])
    # What a responder answers on is what a module may publish to, no more.
    for subject in allowed:
        assert messages.reply_allowed(subject), subject
    for subject in refused:
        assert not messages.reply_allowed(subject), subject
    assert derive().inbox_prefix == messages.module_inbox_prefix(KEY)


def test_bus_topics_are_named_never_wildcarded():
    permissions = derive(
        allow(["bus:*"], ["abi:bus:topic/demo.inbox", "abi:bus:topic/*"])
    )
    assert "demo.inbox.>" in permissions.subscribe
    assert ">" not in permissions.subscribe and "*.>" not in permissions.subscribe
    assert permissions.bus_topics == ("demo.inbox",)


def test_a_topic_queue_is_consumed_never_created_or_changed():
    permissions = derive(allow(["bus:*"], ["abi:bus:topic/demo.inbox"]))
    stream = broker.bus_stream("demo.inbox")
    api = js_api(permissions)
    assert f"$JS.API.CONSUMER.MSG.NEXT.{stream}.>" in api
    assert f"$JS.ACK.{stream}.>" in api
    # Subjects, filters and delivery subjects travel in the request body: the
    # engine creates streams and consumers (abi.broker.v1), and no stream info
    # (a subjects filter would list everyone's subjects).
    assert not any(
        verb in s
        for s in api
        for verb in (".CREATE.", ".UPDATE.", ".PURGE.", ".DELETE.", ".INFO.", "MSG.GET")
    )
    assert "abi.broker.v1.ensure_queue" in permissions.publish


@pytest.mark.parametrize(
    "topic",
    [
        "abi",
        "abi.iam.v1",
        "_INBOX",
        "_INBOX.x",
        "$JS",
        "$SYS.x",
        "evt.x",
        "triple_store",
    ],
)
def test_a_topic_under_a_platform_root_grants_nothing(topic):
    permissions = derive(allow(["bus:*"], [f"abi:bus:topic/{topic}"]))
    assert topic not in permissions.subscribe
    assert f"{topic}.>" not in permissions.subscribe
    assert permissions.bus_topics == ()
    assert broker.reserved_topic_problems([f"abi:bus:topic/{topic}"])


def test_a_topic_claim_check_is_written_never_read_by_direct_get():
    permissions = derive(allow(["bus:*"], ["abi:bus:topic/demo.inbox"]))
    claims = broker.topic_claim_subjects("demo.inbox")
    assert claims in permissions.publish
    # JetStream answers a direct get on the reply subject the module chose,
    # and a stream there would store it: reads go through the engine.
    assert not any("DIRECT.GET" in s for s in permissions.publish)
    assert "abi.broker.v1.read_claim_check" in permissions.publish


# -- jobs -----------------------------------------------------------------------------

OWN_JOBS = allow(
    [
        "discovery:ListJobs",
        "discovery:TriggerJob",
        "discovery:ScheduleJob",
        "discovery:ListJobRuns",
        "discovery:GetJobRun",
        "discovery:CancelJobRun",
    ],
    [
        "abi:discovery:job/acme/people/nightly",
        "abi:discovery:job_run/acme/people/*",
    ],
)


def test_a_module_hosts_the_jobs_its_policy_names():
    permissions = derive(OWN_JOBS)
    mh = broker.module_hash("people")
    jh = broker.job_hash("people", "nightly")
    consumer = broker.job_consumer("people", "nightly")
    trigger = f"abi.jobs.acme.trigger.{mh}.{jh}"
    # It writes nothing into the jobs stream: the engine triggers for it.
    assert not any(s.startswith("abi.jobs.") for s in permissions.publish)
    assert permissions.may_trigger(trigger)
    assert permissions.may_cancel(f"abi.jobs.acme.cancel.{mh}")
    assert f"abi.jobs.acme.cancel.{mh}" in permissions.subscribe
    api = js_api(permissions)
    assert f"$JS.API.CONSUMER.MSG.NEXT.ABI_JOBS_acme.{consumer}" in api
    assert f"$JS.ACK.ABI_JOBS_acme.{consumer}.>" in api
    assert not any(".CREATE." in s or ".INFO." in s for s in api)
    assert permissions.hosted_jobs == (("acme", "nightly"),)


def test_a_host_announces_its_runs_and_a_reader_of_runs_hears_them():
    permissions = derive(OWN_JOBS)
    mh = broker.module_hash("people")
    jh = broker.job_hash("people", "nightly")
    # Its own job's notices out; those of every run it may read (GetJobRun) in.
    assert f"abi.jobdone.acme.{mh}.{jh}" in permissions.publish
    assert f"abi.jobdone.acme.{mh}.*" in permissions.subscribe
    reader = derive(
        allow(["discovery:GetJobRun"], ["abi:discovery:job_run/acme/billing/*"]),
        module=None,
    )
    assert reader.subscribe[-1] == broker.job_done_subject("acme", "billing")
    assert not any(s.startswith("abi.jobdone.") for s in reader.publish)
    # Triggering a job is not reading its runs.
    trigger_only = derive(
        allow(["discovery:TriggerJob"], ["abi:discovery:job/acme/billing/*"])
    )
    assert not any(".jobdone." in s for s in trigger_only.subscribe)


def test_job_subjects_stay_within_the_modules_own():
    permissions = derive(OWN_JOBS)
    mh = broker.module_hash("people")
    for subject in permissions.publish + permissions.subscribe:
        if subject.startswith(("abi.jobs.", "abi.jobdone.")) or "ABI_JOBS_" in subject:
            # Consumer names carry the first 16 characters of the module hash.
            own = mh[:16] in subject
            assert own or subject.startswith("$JS.API.STREAM.INFO."), subject
    api = js_api(permissions)
    # Never the legacy create (its filter is in the body), a purge, or a read
    # of another module's triggers.
    assert not any(".DURABLE.CREATE.ABI_JOBS_" in s for s in api)
    assert not any("STREAM.PURGE" in s or "STREAM.MSG.GET" in s for s in api)


def test_jobs_of_a_named_module_are_triggered_never_hosted():
    permissions = derive(
        allow(["discovery:TriggerJob"], ["abi:discovery:job/acme/billing/*"])
    )
    mh = broker.module_hash("billing")
    assert permissions.may_trigger(f"abi.jobs.acme.trigger.{mh}.{'a' * 32}")
    assert not permissions.may_trigger(
        f"abi.jobs.acme.trigger.{broker.module_hash('other')}.{'a' * 32}"
    )
    assert not any(s.startswith("abi.jobs.") for s in permissions.publish)
    assert not any("cancel" in s for s in permissions.subscribe)
    assert not any("CONSUMER" in s for s in js_api(permissions))


def test_a_job_resource_without_a_module_grants_no_job_subject():
    for resources in (["*"], ["abi:discovery:job/acme/*/*"]):
        permissions = derive(allow(["discovery:TriggerJob"], resources))
        assert not any(s.startswith("abi.jobs.") for s in permissions.publish)
        assert permissions.job_triggers == ()


def test_names_match_the_sdk():
    from naas_abi_sdk import claim_check
    from naas_abi_sdk.bus import BusClient
    from naas_abi_sdk.jobs import job_subjects, stream_name

    subjects = job_subjects("acme", "people", "nightly")
    assert broker.module_hash("people") == subjects.module_hash
    assert broker.job_hash("people", "nightly") == subjects.job_hash
    assert broker.job_consumer("people", "nightly") == subjects.consumer
    assert broker.job_done_subject("acme", "people", "nightly") == subjects.done
    assert broker.jobs_stream("acme") == stream_name("acme")
    assert broker.bus_stream("x.y") == BusClient.stream_name("x.y")
    assert broker.CLAIM_CHECK_STREAM == claim_check.STREAM
    assert broker.topic_claim_subjects("x.y") == (
        f"abi.cc.{claim_check.topic_scope('x.y')}.>"
    )
    assert broker.job_claim_subjects("acme", "people") == (
        f"abi.cc.{claim_check.job_scope('acme', subjects.module_hash)}.>"
    )


def test_an_account_that_is_not_a_modules_hosts_nothing():
    permissions = derive(OWN_JOBS, module=None)
    # Its inbox, and the notices of the runs it may read: no cancels to host.
    assert permissions.subscribe == (
        f"_INBOX.{KEY}.m.>",
        broker.job_done_subject("acme", "people"),
    )
    assert not any("CONSUMER" in s for s in js_api(permissions))


def test_broker_operations_are_the_sdks():
    from naas_abi_sdk.broker_control import OPERATIONS

    assert broker.BROKER_OPERATIONS == OPERATIONS


def test_nested_topics_are_refused_the_same_topic_is_shared():
    assert broker.nested_topic_problems(["orders"], ["orders.eu"])
    assert broker.nested_topic_problems(["orders.eu"], ["orders"])
    assert broker.nested_topic_problems(["orders", "orders.eu"], [])
    assert broker.nested_topic_problems(["orders"], ["orders"]) == []
    assert broker.nested_topic_problems(["orders"], ["ordersx"]) == []


def test_subject_matching_is_natss():
    assert broker.subject_matches("a.*.c", "a.b.c")
    assert not broker.subject_matches("a.*.c", "a.b.c.d")
    assert broker.subject_matches("a.>", "a.b.c")
    assert not broker.subject_matches("a.>", "a")
    assert not broker.subject_matches("a.b", "a.c")


def test_a_connection_is_renewed_well_before_the_broker_expires_it():
    from naas_abi_sdk import credentials

    from naas_abi_core.engine import nats_auth_callout as callout
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        NATSAuthCalloutConfiguration,
    )

    assert credentials.CONNECTION_TTL_SECONDS == callout.MAX_USER_TTL_SECONDS
    # The configuration's shortest lifetime still leaves a renewal's margin.
    shortest = NATSAuthCalloutConfiguration.model_fields["user_ttl_seconds"]
    minimum = next(m.ge for m in shortest.metadata if hasattr(m, "ge"))
    assert credentials.RENEW_CONNECTION_SECONDS * 2 <= minimum
    # ... and no longer than an access token lives.
    maximum = next(m.le for m in shortest.metadata if hasattr(m, "le"))
    assert maximum <= 600


def test_no_account_is_offered_an_iam_mutation_without_its_action():
    """A module hosting an agent reads its caller's token: whatever that token
    may do at IAM, the module's own connection must not even reach the
    operations that change who may do what."""
    nothing = derive()
    for operation in (
        "attach_policy",
        "detach_policy",
        "create_key",
        "revoke_key",
        "revoke_tokens",
        "approve_manifest",
        "reject_manifest",
        "create_policy",
        "create_service_account",
        "put_placement",
        "register_catalog",
        "suspend_principal",
    ):
        assert f"abi.iam.v1.{operation}" not in nothing.publish, operation
    assert {s for s in nothing.publish if s.startswith("abi.iam.v1.")} == {
        f"abi.iam.v1.{op}" for op in broker.IAM_ALWAYS
    }
    # ... and gets exactly the one it is allowed.
    granted = derive(allow(["iam:ListKeys"]), catalogs=kernel_with_iam())
    assert "abi.iam.v1.list_keys" in granted.publish
    assert "abi.iam.v1.create_key" not in granted.publish


def test_iam_always_names_are_iam_operations():
    assert set(broker.IAM_ALWAYS) <= set(broker.IAM_OPERATIONS)


def kernel_with_iam() -> CatalogRegistry:
    from naas_abi_core.services.iam.iam_catalog import CATALOG

    registry = kernel()
    registry.register(CATALOG)
    return registry


def test_a_deny_of_a_topic_holds_whatever_the_allow_spells_it():
    # ``or%64ers`` decodes to ``orders``: the subjects follow the decoded name.
    permissions = derive(
        allow(["bus:*"], ["abi:bus:topic/or%64ers"]),
        Statement("Deny", ("bus:Consume",), ("abi:bus:topic/orders",)),
    )
    assert permissions.bus_consume == ()
    assert permissions.bus_publish == ("orders",)
    assert not any(s.startswith("orders") for s in permissions.subscribe)


@pytest.mark.parametrize(
    "topic", ["x.${principal.id}", "${user.id}", "pay%24%7Bprincipal.id%7D"]
)
def test_a_topic_naming_a_variable_grants_nothing(topic):
    """Nothing substitutes a variable here: the topic would be granted as written."""
    permissions = derive(allow(["bus:*"], [f"abi:bus:topic/{topic}"]))
    assert permissions.bus_topics == ()
    assert permissions.bus_publish == ()
    assert broker.reserved_topic_problems([f"abi:bus:topic/{topic}"])
