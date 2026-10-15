import pytest

from naas_abi_core.services.iam import broker
from naas_abi_core.services.iam.adapters import iam_nats_codec
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import EffectiveStatement
from naas_abi_core.services.iam.policy import Statement

ACCOUNT = "sa_01jabcdefghjkmnpqrstvwxyz0"
SA = "01jabcdefghjkmnpqrstvwxyz0"
KEY = "abcdefghijklmnop"


def derive(*statements: Statement, module=("acme", "people")):
    return broker.derive(
        principal_id=ACCOUNT,
        key_id=KEY,
        statements=[EffectiveStatement(s, "p", i) for i, s in enumerate(statements)],
        catalogs=CatalogRegistry(),
        module=module,
    )


def allow(actions, resources=("*",)):
    return Statement("Allow", tuple(actions), tuple(resources))


def js_api(permissions):
    return [s for s in permissions.publish if s.startswith("$JS.")]


def test_nothing_granted_reaches_iam_requests_its_inbox_and_its_hosting_only():
    permissions = derive()
    assert "abi.iam.v1.token" in permissions.publish
    assert "abi.iam.v1.submit_manifest" in permissions.publish
    assert "_INBOX.>" in permissions.publish
    assert "abi.rpc.overflow.>" in permissions.publish
    assert js_api(permissions) == []
    assert permissions.subscribe == (
        f"_INBOX.{KEY}.>",
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
        allow(["discovery:InvokeAgent"], ["abi:-:-:discovery:agent/beta/research/*"]),
        module=None,
    )
    assert "abi.discovery.beta.v1.>" in permissions.publish
    assert "abi.agent.beta.*.*.*.v1.*" in permissions.publish
    anywhere = derive(allow(["discovery:InvokeAgent"]), module=None)
    assert "abi.discovery.*.v1.>" in anywhere.publish


def test_a_service_wildcard_reaches_the_service_and_its_live_subjects():
    permissions = derive(allow(["event:*"]))
    assert "abi.svc.event.v1.>" in permissions.publish
    assert "evt.>" in permissions.subscribe


def test_a_deny_on_everything_takes_the_service_back():
    permissions = derive(
        allow(["keyvalue:*"]), Statement("Deny", ("keyvalue:*",), ("*",))
    )
    assert "abi.svc.keyvalue.v1.>" not in permissions.publish


# -- bus ------------------------------------------------------------------------------


def test_bus_topics_are_named_never_wildcarded():
    permissions = derive(
        allow(["bus:*"], ["abi:-:-:bus:topic/demo.inbox", "abi:-:-:bus:topic/*"])
    )
    assert "demo.inbox.>" in permissions.subscribe
    assert ">" not in permissions.subscribe and "*.>" not in permissions.subscribe
    assert permissions.bus_topics == ("demo.inbox",)


def test_a_topic_queue_is_consumed_never_created_or_changed():
    permissions = derive(allow(["bus:*"], ["abi:-:-:bus:topic/demo.inbox"]))
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
    "topic", ["abi", "abi.iam.v1", "_INBOX", "_INBOX.x", "$JS", "$SYS.x", "evt.x"]
)
def test_a_topic_under_a_platform_root_grants_nothing(topic):
    permissions = derive(allow(["bus:*"], [f"abi:-:-:bus:topic/{topic}"]))
    assert topic not in permissions.subscribe
    assert f"{topic}.>" not in permissions.subscribe
    assert permissions.bus_topics == ()
    assert broker.reserved_topic_problems([f"abi:-:-:bus:topic/{topic}"])


def test_a_topic_claim_check_is_written_never_read_by_direct_get():
    permissions = derive(allow(["bus:*"], ["abi:-:-:bus:topic/demo.inbox"]))
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
        "abi:-:-:discovery:job/acme/people/nightly",
        "abi:-:-:discovery:job_run/acme/people/*",
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


def test_job_subjects_stay_within_the_modules_own():
    permissions = derive(OWN_JOBS)
    mh = broker.module_hash("people")
    for subject in permissions.publish + permissions.subscribe:
        if subject.startswith("abi.jobs.") or "ABI_JOBS_" in subject:
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
        allow(["discovery:TriggerJob"], ["abi:-:-:discovery:job/acme/billing/*"])
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
    for resources in (["*"], ["abi:-:-:discovery:job/acme/*/*"]):
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
    assert permissions.subscribe == (f"_INBOX.{KEY}.>",)
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
