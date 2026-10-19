"""Broker permissions of a service account, from its policy (RFC §8.4).

The NATS auth callout gives each module connection the subjects this module
derives. The broker grants at the operation level: a service the account may
call at all, whatever resource; resource-level decisions stay in the domain
services.

A permission ending in ``*`` also lets a client name that token ``>`` or
``*``: nats-server matches a published subject's tokens literally. So every
grant here keeps the account's own tokens before its first wildcard, and none
reaches a subject space shared with other accounts.

No connection gets response permissions: they would let a module answer any
reply subject of a message it receives, and a module chooses the reply
subject of the messages it sends to itself. It answers requests on
``_INBOX.>``, where every client receives its replies (and every responder
answers there only, ``naas_abi_sdk.messages.reply_allowed``).

* **Always**: IAM's read-only and self-service request subjects
  (``IAM_ALWAYS``: ``token``, ``exchange_token``, ``jwks``, ``submit_manifest``, ``get_manifest``,
  ``find_service_account``, ``authorize``, ``filter``; never a mutation, never
  ``abi.iam.v1.changed``); the others only for an ``iam:`` action the policy
  allows; the engine's broker
  control (``abi.broker.v1.<operation>``: it checks each request against the
  same grants); messages to inboxes (``_INBOX.>``: replies, an app's request
  body to pull, a submitter's run updates: random names); its own inbox
  prefix, ``_INBOX.<key id>``, the only inboxes it may read (the SDK sets
  it); the RPC overflow host (``abi.rpc.overflow.>``), whose sessions belong
  to the caller that opened them.
* **Hosting**, for a module's account: ``abi.agent.<project>.<sa>.>`` and
  ``abi.mod.<project>.<sa>.>``, ``<sa>`` being its id's ULID part; and the jobs
  its policy names (below).
* **Each action an Allow grants**, unless a Deny on every resource takes it
  back: the action's catalog subjects when its service registered a catalog,
  else the service's whole subject space (``abi.svc.<service>.v1.>``).
  Discovery actions add the hosting subjects of the modules they reach.
* **Jobs**, from the job resources a discovery job action names
  (``job/<project>/<module>/<job>``, module named): the triggers and cancels
  the engine publishes for it on those modules' jobs only (``job_triggers``,
  ``job_cancels``), and their triggers' claim checks. A module's own named jobs
  are hosted: fetching from and acknowledging its consumers, its cancel
  subject, reading its triggers' claim checks. A module writes nothing into
  the jobs stream: its schedules make the server allow rollups there.
* **Bus topics** named ``abi:-:-:bus:topic/<topic>`` (a concrete topic, none
  under a reserved root), by action: ``bus:Publish`` publishes on the topic
  and writes its claim checks; ``bus:Consume`` subscribes to it and fetches
  from and acknowledges the consumers of its queue stream. A Deny of an
  action on a topic keeps that topic from it.
* **Live events** (``evt.>``): ``event:Append`` publishes, and the read
  actions (``Query``, ``QueryStream``, ``QueryForConsumer``) subscribe.
  Listing types or cursors reaches neither.
* **Claim checks** are read through the engine (``read_claim_check``), never
  by direct get: JetStream answers on the reply subject the requester chose,
  and a stream there would store a message of the module's choosing, headers
  and all.
* **Streams and consumers are created by the engine**, never by a module
  (``abi.broker.v1``, ``engine/nats_broker_control.py``): their subjects and
  delivery subjects travel in the request body, which the broker never
  reads. No stream info either: a subjects filter would list every module's
  subjects.
* Everything else is denied, ``$SYS.>`` and the rest of ``$JS.API.>``
  included.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import EffectiveStatement
from naas_abi_core.services.iam.names import matches

# IAM's operations (adapters/iam_nats_codec.OPERATIONS; a test keeps them in
# step). Every account may ask: IAM authorizes each one itself.
IAM_OPERATIONS = (
    "add_group_member",
    "approve_manifest",
    "attach_policy",
    "authorize",
    "bind_idp_group",
    "claim_pending_grants",
    "create_group",
    "create_key",
    "create_pending_grant",
    "create_policy",
    "create_service_account",
    "delete_group",
    "delete_placement",
    "delete_policy",
    "delete_principal",
    "delete_scope",
    "detach_policy",
    "ensure_user",
    "exchange_token",
    "explain",
    "filter",
    "find_service_account",
    "get_group",
    "get_manifest",
    "get_policy",
    "get_principal",
    "jwks",
    "list_attachments",
    "list_group_members",
    "list_groups",
    "list_idp_bindings",
    "list_idp_group_mappings",
    "list_keys",
    "list_manifests",
    "list_pending_grants",
    "list_placements",
    "list_policies",
    "list_principals",
    "map_idp_group",
    "put_placement",
    "put_scope",
    "register_catalog",
    "reject_manifest",
    "remove_group_member",
    "resume_principal",
    "revoke_key",
    "revoke_pending_grant",
    "revoke_tokens",
    "submit_manifest",
    "suspend_principal",
    "token",
    "unbind_idp_group",
    "unmap_idp_group",
    "update_policy",
)
# naas_abi_sdk.broker_control.OPERATIONS (a test keeps them in step).
BROKER_OPERATIONS = (
    "ensure_topic",
    "ensure_queue",
    "ensure_job",
    "set_schedules",
    "trigger",
    "cancel",
    "ensure_claim_checks",
    "read_claim_check",
    "verify_trigger",
)
# What every account may ask of IAM: its own key exchange, the public JWKS, its
# own manifest, the renewal of a delegation it holds (``exchange_token``: IAM
# asks for ``iam:ExchangeToken`` of anyone else, and a token exchange changes
# nothing stored), and read-only questions about the policy as it stands. IAM
# decides each, but the broker offers nothing that changes IAM: an account
# holds the others only by the ``iam:`` actions its policy allows, like any
# other service's.
IAM_ALWAYS = (
    "token",
    "exchange_token",
    "jwks",
    "submit_manifest",
    "get_manifest",
    "find_service_account",
    "authorize",
    "filter",
)
ALWAYS_PUBLISH = (
    *(f"abi.iam.v1.{operation}" for operation in IAM_ALWAYS),
    *(f"abi.broker.v1.{operation}" for operation in BROKER_OPERATIONS),
    # Inboxes it is handed (random names it never subscribes to but its own).
    "_INBOX.>",
    # Requests and replies above the broker limit: sessions bound to the caller.
    "abi.rpc.overflow.>",
)
# Live pub/sub of a service besides its request subjects: per action, what it
# lets a module publish and subscribe. Any other action of the service reaches
# neither.
LIVE_SUBJECTS = {"event": ("evt.>",)}
LIVE_PUBLISH_ACTIONS = {"event": ("Append",)}
LIVE_SUBSCRIBE_ACTIONS = {"event": ("Query", "QueryStream", "QueryForConsumer")}
# The bus has no catalog: its two actions, publishing (and enqueueing) on a
# topic, and consuming from it (subscribing, dequeuing).
BUS_ACTIONS = ("Publish", "Consume")
# Kernel services served under abi.svc.<service>.v1 (iam and discovery have
# their own subjects).
KERNEL_SERVICES = (
    "activity_log",
    "cache",
    "coding_environment",
    "dataset",
    "document",
    "email",
    "event",
    "keyvalue",
    "model_registry",
    "object_storage",
    "secret",
    "source_control",
    "triple_store",
    "vector_store",
)
# Bus topics may not start with these: their subjects belong to the platform.
# ``triple_store`` is the topic the triple store broadcasts every graph's
# changes on: the bus checks no subscriber, so a module reads graphs through
# ``triple_store:Subscribe``, never by naming the topic.
RESERVED_TOPIC_ROOTS = ("abi", "evt", "_INBOX", "triple_store")
TOPIC_PREFIX = "abi:-:-:bus:topic/"

# Names shared with naas_abi_sdk (claim_check, jobs, bus); a test keeps them equal.
CLAIM_CHECK_STREAM = "ABI_CLAIM_CHECKS"
CLAIM_CHECK_PREFIX = "abi.cc"
JOB_ACTIONS = (
    "ListJobs",
    "TriggerJob",
    "ScheduleJob",
    "ListJobRuns",
    "GetJobRun",
    "CancelJobRun",
)


@dataclass(frozen=True)
class BrokerPermissions:
    publish: tuple[str, ...]
    subscribe: tuple[str, ...]
    inbox_prefix: str
    allow_responses: bool = True
    services: tuple[str, ...] = field(default=())
    # What the engine creates before the connection is admitted.
    bus_topics: tuple[str, ...] = field(default=())
    # ... by action: the topics it may publish on (bus:Publish) and consume
    # from (bus:Consume); ``bus_topics`` is every topic either names.
    bus_publish: tuple[str, ...] = field(default=())
    bus_consume: tuple[str, ...] = field(default=())
    claim_checks: bool = False
    # The module's own jobs, (project, job): their consumers the engine creates.
    hosted_jobs: tuple[tuple[str, str], ...] = field(default=())
    # Trigger and cancel subjects (patterns) the engine publishes on for it: a
    # module writes nothing into the jobs stream itself.
    job_triggers: tuple[str, ...] = field(default=())
    job_cancels: tuple[str, ...] = field(default=())

    def may_trigger(self, subject: str) -> bool:
        return any(subject_matches(p, subject) for p in self.job_triggers)

    def may_cancel(self, subject: str) -> bool:
        return any(subject_matches(p, subject) for p in self.job_cancels)


def subject_matches(pattern: str, subject: str) -> bool:
    """NATS matching of a concrete ``subject`` against ``pattern``."""
    want, got = pattern.split("."), subject.split(".")
    for index, token in enumerate(want):
        if token == ">":
            return len(got) > index
        if index >= len(got) or (token != "*" and token != got[index]):
            return False
    return len(got) == len(want)


def hosting_subjects(project: str, principal_id: str) -> tuple[str, ...]:
    from naas_abi_core.services.iam.modules import subject_token

    sa = subject_token(principal_id)
    return (f"abi.agent.{project}.{sa}.>", f"abi.mod.{project}.{sa}.>")


# --- names shared with the SDK -----------------------------------------------------------


def _hash(*values: str) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


def bus_stream(topic: str) -> str:
    """The JetStream stream of a bus topic's queues (``BusClient.stream_name``)."""
    return "naas-abi-" + hashlib.sha256(topic.encode()).hexdigest()


def jobs_stream(project: str) -> str:
    return f"ABI_JOBS_{project}"


def module_hash(module_id: str) -> str:
    return _hash(module_id)[:32]


def job_hash(module_id: str, job: str) -> str:
    return _hash(module_id, job)[:32]


def job_consumer(module_id: str, job: str) -> str:
    return f"job-{module_hash(module_id)[:16]}-{job_hash(module_id, job)[:16]}"


def topic_claim_subjects(topic: str) -> str:
    return f"{CLAIM_CHECK_PREFIX}.t.{hashlib.sha256(topic.encode()).hexdigest()[:32]}.>"


def job_claim_subjects(project: str, module_id: str) -> str:
    return f"{CLAIM_CHECK_PREFIX}.j.{project}.{module_hash(module_id)}.>"


# --- topics ------------------------------------------------------------------------------


def topic_problem(topic: str) -> str | None:
    """Why ``topic`` cannot be granted, or None."""
    if not topic:
        return "a bus topic is not empty"
    if any(c in topic for c in "*>? \t\r\n"):
        return f"bus topic {topic!r} has a wildcard or a space"
    tokens = topic.split(".")
    if any(not t for t in tokens):
        return f"bus topic {topic!r} has an empty token"
    root = tokens[0]
    if root in RESERVED_TOPIC_ROOTS or root.startswith(("$", "_")):
        return f"bus topic {topic!r} is under {root!r}, reserved for the platform"
    return None


def reserved_topic_problems(resources: Iterable[str]) -> list[str]:
    """Why the concrete bus topics among ``resources`` cannot be granted.
    (A topic pattern is no error: it grants no subject.)"""
    found = []
    for resource in resources:
        if resource.startswith(TOPIC_PREFIX):
            topic = unquote(resource[len(TOPIC_PREFIX) :])
            problem = topic_problem(topic)
            if problem is not None and not any(c in topic for c in "*?"):
                found.append(problem)
    return found


def topics_of(statements: Iterable[object]) -> list[str]:
    """The grantable bus topics a policy document's Allow statements name."""
    found: list[str] = []
    for statement in statements:
        if getattr(statement, "effect", "Allow") != "Allow":
            continue
        for topic in _topics(getattr(statement, "resources", ())):
            if topic not in found:
                found.append(topic)
    return found


def nested_topic_problems(topics: Iterable[str], others: Iterable[str]) -> list[str]:
    """Topics nested in one another: a grant covers ``<topic>.>``, so a module
    granted ``orders`` would read and write ``orders.eu``, and JetStream
    refuses overlapping queue streams. The same topic twice is shared, fine."""
    mine, theirs = list(topics), list(others)
    problems = []
    for topic in mine:
        for other in [*mine, *theirs]:
            if other != topic and other.startswith(topic + "."):
                problems.append(
                    f"bus topic {topic!r} contains approved topic {other!r}"
                )
            elif other != topic and topic.startswith(other + "."):
                problems.append(
                    f"bus topic {topic!r} is inside approved topic {other!r}"
                )
    return sorted(set(problems))


def _topics(resources: Iterable[str]) -> list[str]:
    """Bus topics named ``abi:-:-:bus:topic/<topic>``: concrete, not reserved.
    A topic pattern would reach other connections' subjects."""
    topics = []
    for resource in resources:
        if resource.startswith(TOPIC_PREFIX):
            topic = unquote(resource[len(TOPIC_PREFIX) :])
            if topic_problem(topic) is None and topic not in topics:
                topics.append(topic)
    return topics


# --- derivation --------------------------------------------------------------------------


def derive(
    *,
    principal_id: str,
    key_id: str,
    statements: Iterable[EffectiveStatement],
    catalogs: CatalogRegistry,
    module: tuple[str, str] | None,
) -> BrokerPermissions:
    """The subjects of a connection authenticated by ``key_id``.

    ``module`` is ``(project, module_id)`` for a module's account.
    """
    inbox = f"_INBOX.{key_id}"
    allows: list[EffectiveStatement] = []
    blanket_denies: list[str] = []
    # Denies of one resource: (action patterns, resource patterns). Only bus
    # topics are decided per resource here; the services decide the rest.
    resource_denies: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for effective in statements:
        statement = effective.statement
        if statement.effect == "Deny":
            if any(r == "*" for r in statement.resources):
                blanket_denies += statement.actions
            resource_denies.append(
                (tuple(statement.actions), tuple(statement.resources))
            )
        else:
            allows.append(effective)

    def denied(action: str, resource: str) -> bool:
        return any(
            any(matches(a, action) for a in actions)
            and any(matches(r, resource) for r in resources)
            for actions, resources in resource_denies
        )

    publish: list[str] = list(ALWAYS_PUBLISH)
    subscribe: list[str] = [f"{inbox}.>"]
    services: set[str] = set()
    topics: list[str] = []
    bus_publish: list[str] = []
    bus_consume: list[str] = []
    claim_checks = False
    own_project = module[0] if module else None
    if module is not None:
        subscribe += hosting_subjects(module[0], principal_id)

    def add(target: list[str], subjects: Iterable[str]) -> None:
        for subject in subjects:
            if subject not in target:
                target.append(subject)

    hosted: set[tuple[str, str]] = set()  # own (project, job) to host
    job_triggers: list[str] = []
    job_cancels: list[str] = []
    for effective in allows:
        resources = effective.statement.resources
        for pattern in effective.statement.actions:
            for service, action in _actions(pattern, catalogs):
                qualified = f"{service}:{action}" if action else f"{service}:*"
                if any(matches(deny, qualified) for deny in blanket_denies):
                    continue
                services.add(service)
                if service == "discovery":
                    for project in _projects(own_project, resources):
                        add(publish, _discovery_subjects(action, project))
                    if action is None or action in JOB_ACTIONS:
                        reach = _job_subjects(action, resources, module)
                        add(job_triggers, reach.triggers)
                        add(job_cancels, reach.cancels)
                        add(publish, reach.claim_writes)
                        if reach.claim_writes:
                            claim_checks = True
                        hosted |= reach.hosted
                    continue
                add(publish, _subjects(service, action, catalogs))
                if action is None or action in LIVE_PUBLISH_ACTIONS.get(service, ()):
                    add(publish, LIVE_SUBJECTS.get(service, ()))
                if action is None or action in LIVE_SUBSCRIBE_ACTIONS.get(service, ()):
                    add(subscribe, LIVE_SUBJECTS.get(service, ()))
                if service == "bus":
                    for resource in resources:
                        for topic in _topics((resource,)):
                            _bus_topic(
                                action,
                                topic,
                                resource,
                                denied=denied,
                                topics=topics,
                                bus_publish=bus_publish,
                                bus_consume=bus_consume,
                                publish=publish,
                                subscribe=subscribe,
                            )
                            claim_checks = True
    if module is not None:
        for project, job in sorted(hosted):
            add(publish, _job_host_api(project, module[1], job))
            add(subscribe, (f"abi.jobs.{project}.cancel.{module_hash(module[1])}",))
            # Its own jobs: triggered (event bridges, self-triggers) and their
            # runs cancelled through the engine.
            mh, jh = module_hash(module[1]), job_hash(module[1], job)
            add(job_triggers, (f"abi.jobs.{project}.trigger.{mh}.{jh}",))
            add(job_cancels, (f"abi.jobs.{project}.cancel.{mh}",))
            add(publish, _claim_check_api(job_claim_subjects(project, module[1])))
            claim_checks = True
    return BrokerPermissions(
        publish=tuple(publish),
        subscribe=tuple(subscribe),
        inbox_prefix=inbox,
        services=tuple(sorted(services)),
        bus_topics=tuple(topics),
        bus_publish=tuple(bus_publish),
        bus_consume=tuple(bus_consume),
        claim_checks=claim_checks,
        hosted_jobs=tuple(sorted(hosted)) if module is not None else (),
        job_triggers=tuple(job_triggers),
        job_cancels=tuple(job_cancels),
    )


def _bus_topic(
    action: str | None,
    topic: str,
    resource: str,
    *,
    denied: Callable[[str, str], bool],
    topics: list[str],
    bus_publish: list[str],
    bus_consume: list[str],
    publish: list[str],
    subscribe: list[str],
) -> None:
    """One topic's subjects for one bus action: ``Publish`` writes, ``Consume``
    reads (subscribes, fetches and acknowledges). Another action reaches
    nothing, and a Deny of an action on the topic keeps it from that action."""

    def add(target: list[str], subjects: Iterable[str]) -> None:
        for subject in subjects:
            if subject not in target:
                target.append(subject)

    # The subjects come from the percent-decoded topic, so a Deny is matched
    # against every spelling of it: ``topic/or%64ers`` is ``topic/orders``.
    spellings = {resource, TOPIC_PREFIX + topic, TOPIC_PREFIX + quote(topic, safe="")}
    for name in BUS_ACTIONS if action is None else (action,):
        if name not in BUS_ACTIONS or any(
            denied(f"bus:{name}", spelling) for spelling in spellings
        ):
            continue
        add(topics, (topic,))
        if name == "Publish":
            add(bus_publish, (topic,))
            add(publish, (topic, f"{topic}.>"))
            add(publish, _claim_check_api(topic_claim_subjects(topic)))
        else:
            add(bus_consume, (topic,))
            add(subscribe, (topic, f"{topic}.>"))
            add(publish, _queue_api(bus_stream(topic)))


def _actions(pattern: str, catalogs: CatalogRegistry) -> list[tuple[str, str | None]]:
    """``(service, action)`` pairs an action pattern reaches; action None means
    every action of a service without a catalog."""
    service_pattern, _, action_pattern = pattern.partition(":")
    if pattern == "*":
        service_pattern, action_pattern = "*", "*"
    known = sorted(set(KERNEL_SERVICES) | {"iam", "identity", "discovery", "bus"})
    found: list[tuple[str, str | None]] = []
    for service in known:
        if not matches(service_pattern, service):
            continue
        catalog = catalogs.get(service)
        if catalog is None and service == "bus":
            found += [
                ("bus", name) for name in BUS_ACTIONS if matches(action_pattern, name)
            ]
            continue
        if catalog is None:
            # No catalog to expand a wildcard against: a concrete action keeps
            # its name (discovery:Register reaches registration subjects only).
            wildcard = "*" in action_pattern or "?" in action_pattern
            found.append((service, None if wildcard else action_pattern))
            continue
        for spec in catalog.actions:
            if matches(action_pattern, spec.name):
                found.append((service, spec.name))
    return found


def _subjects(service: str, action: str | None, catalogs: CatalogRegistry) -> list[str]:
    if service == "bus":
        return []  # its topics
    catalog = catalogs.get(service)
    if service == "iam" and (catalog is None or action is None):
        # Every operation, but never the change notice (a policy of ``*``).
        return [f"abi.iam.v1.{op}" for op in IAM_OPERATIONS] if action is None else []
    if catalog is not None and action is not None:
        spec = next((a for a in catalog.actions if a.name == action), None)
        return list(spec.subjects) if spec is not None else []
    if service == "identity":
        return ["abi.identity.v1.>"]  # a kernel service outside abi.svc
    return [f"abi.svc.{service}.v1.>"]


# --- discovery ---------------------------------------------------------------------------


def _segments(resource: str, service: str) -> tuple[str, list[str]] | None:
    """``(type, id segments)`` of a resource pattern of ``service``; ``("*",
    ["*"])`` for one that reaches every resource of it; None for another
    service's."""
    if resource == "*":
        return "*", ["*"]
    fields = resource.split(":", 4)
    if len(fields) != 5 or fields[0] != "abi":
        return None
    if not matches(fields[3], service):
        return None
    type_, _, id_ = fields[4].partition("/")
    if "*" in type_ or "?" in type_:
        return "*", ["*"]
    return type_, [unquote(part) for part in id_.split("/")] if id_ else ["*"]


def _concrete(value: str) -> bool:
    return bool(value) and not any(c in value for c in "*?") and "." not in value


def _projects(own: str | None, resources: Iterable[str]) -> list[str]:
    """The discovery projects a statement reaches: a module's own; for another
    account, those its resources name (``<type>/<project>/...``), ``*`` for
    any."""
    if own is not None:
        return [own]
    projects: list[str] = []
    for resource in resources:
        found = _segments(resource, "discovery")
        if found is None:
            continue
        project = found[1][0] if found[1] else "*"
        project = project if _concrete(project) else "*"
        if project not in projects:
            projects.append(project)
    return ["*"] if "*" in projects else projects


def _discovery_subjects(action: str | None, project: str) -> list[str]:
    subjects = [f"abi.discovery.{project}.v1.>"]
    reach = {
        "InvokeAgent": [f"abi.agent.{project}.*.*.*.v1.*"],
        "GetAgentRun": [f"abi.agent.{project}.*.*.*.v1.*"],
        "CancelAgentRun": [f"abi.agent.{project}.*.*.*.v1.*"],
        "ChatModel": [f"abi.mod.{project}.*.*.model.*.chat"],
        "OpenApp": [f"abi.mod.{project}.*.*.app.*.http"],
    }
    if action is None:
        for extra in reach.values():
            subjects += [s for s in extra if s not in subjects]
    else:
        subjects += reach.get(action, [])
    return subjects


# --- jobs --------------------------------------------------------------------------------


@dataclass
class _JobReach:
    triggers: list[str] = field(default_factory=list)
    cancels: list[str] = field(default_factory=list)
    claim_writes: list[str] = field(default_factory=list)
    hosted: set[tuple[str, str]] = field(default_factory=set)


def _job_subjects(
    action: str | None,
    resources: Iterable[str],
    module: tuple[str, str] | None,
) -> _JobReach:
    """The named modules' jobs a statement reaches: their trigger and cancel
    subjects (published by the engine for the account), the claim checks of
    their triggers (written by the account), and the module's own named jobs
    to host. A job resource without a concrete project and module reaches no
    subject: hashes cannot be wildcarded per module."""
    actions = JOB_ACTIONS if action is None else (action,)
    reach = _JobReach()
    for resource in resources:
        found = _segments(resource, "discovery")
        if found is None:
            continue
        type_, parts = found
        if type_ not in ("job", "job_run") or len(parts) < 2:
            continue
        project, module_id = parts[0], parts[1]
        if not (_concrete(project) and module_id and "*" not in module_id):
            continue
        job = parts[2] if len(parts) > 2 and type_ == "job" else "*"
        concrete_job = bool(job) and "*" not in job and "?" not in job
        mh = module_hash(module_id)
        jh = job_hash(module_id, job) if concrete_job else "*"
        if type_ == "job":
            if "TriggerJob" in actions:
                reach.triggers.append(f"abi.jobs.{project}.trigger.{mh}.{jh}")
                reach.claim_writes += _claim_check_writes(
                    job_claim_subjects(project, module_id)
                )
            if module == (project, module_id) and concrete_job:
                reach.hosted.add((project, job))
        if "CancelJobRun" in actions:
            reach.cancels.append(f"abi.jobs.{project}.cancel.{mh}")
    return reach


def _job_host_api(project: str, module_id: str, job: str) -> list[str]:
    """What a module's job host uses for one of its jobs, in the engine's jobs
    stream: fetching from and acknowledging its own consumer (the engine
    creates it, writes its schedules and triggers). Nothing else: the
    stream allows rollups (schedules need them), so one write of a module
    with ``Nats-Rollup: all`` would purge every module's jobs."""
    stream = jobs_stream(project)
    consumer = job_consumer(module_id, job)
    return [
        f"$JS.API.CONSUMER.MSG.NEXT.{stream}.{consumer}",
        f"$JS.ACK.{stream}.{consumer}.>",
    ]


# --- streams the engine creates ------------------------------------------------------------


def _queue_api(stream: str) -> list[str]:
    """A bus topic's queue stream: fetching from and acknowledging its
    consumers (the engine creates them). Never a stream or consumer creation,
    update, purge, deletion or info."""
    return [
        f"$JS.API.CONSUMER.MSG.NEXT.{stream}.>",
        f"$JS.ACK.{stream}.>",
    ]


def _claim_check_writes(subjects: str) -> list[str]:
    return [subjects]


def _claim_check_api(subjects: str) -> list[str]:
    """Write the claim checks under ``subjects``. Reading goes through the
    engine (``read_claim_check``): JetStream answers a direct get on the
    reply subject the requester chose, and a stream there stores the answer,
    headers and all."""
    return _claim_check_writes(subjects)
