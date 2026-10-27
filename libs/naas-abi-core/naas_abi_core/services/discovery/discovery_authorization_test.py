"""Using what a module serves needs the caller's policy, not only a READY provider."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.services.discovery.discovery_service import (
    DiscoveryError,
    DiscoveryService,
)
from naas_abi_core.services.discovery.discovery_service_test import (
    MemoryRegistry,
    registration,
)
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.iam.names import parse_resource_name
from naas_abi_core.services.iam.tests.authorization_contract import contract_iam
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

PROVIDER = "provider-identity"
MODULE = "abi:-:-:discovery:"


def _provider() -> pb.RegisterRequest:
    req = registration("research", "instance")
    req.descriptor.agents.add(
        name="Researcher", contract_major=1, capabilities=["agent.invoke.v1"]
    )
    req.descriptor.models.add(name="writer", kind="chat")
    req.descriptor.apps.add(name="console", contract_major=1)
    req.descriptor.jobs.add(
        name="ingest",
        contract_major=1,
        triggers=[pb.JobTrigger(kind="cron", spec="0 0 6 * * *")],
        max_concurrency=1,
        max_attempts=1,
    )
    return req


async def _ready(service: DiscoveryService) -> pb.RegisterRequest:
    req = _provider()
    with as_service_account("engine"):
        await service.register(req, PROVIDER)
        await service.renew(
            pb.RenewRequest(
                instance_id="instance", lease_token=req.lease_token, initialized=True
            ),
            PROVIDER,
        )
    return req


def _uses(req: pb.RegisterRequest):
    """Each use of what the provider serves, as (action, resource, call)."""
    lease: dict[str, Any] = {"instance_id": "instance", "lease_token": req.lease_token}
    return [
        (
            "discovery:InvokeAgent",
            f"{MODULE}agent/default/research/Researcher",
            "AGENT_NOT_FOUND",
            lambda s, caller: s.authorize_agent(
                pb.AuthorizeAgentRequest(
                    **lease, agent_name="Researcher", new_invocation=True
                ),
                PROVIDER,
                caller,
            ),
        ),
        (
            "discovery:ChatModel",
            f"{MODULE}model/default/research/writer",
            "MODEL_NOT_FOUND",
            lambda s, caller: s.authorize_model(
                pb.AuthorizeModelRequest(**lease, model_name="writer"),
                PROVIDER,
                caller,
            ),
        ),
        (
            "discovery:OpenApp",
            f"{MODULE}app/default/research/console",
            "APP_NOT_FOUND",
            lambda s, caller: s.authorize_app(
                pb.AuthorizeAppRequest(**lease, app_name="console"), PROVIDER, caller
            ),
        ),
        (
            "discovery:TriggerJob",
            f"{MODULE}job/default/research/ingest",
            "JOB_NOT_FOUND",
            lambda s, caller: s.authorize_job(
                pb.AuthorizeJobRequest(**lease, job_name="ingest", operation="trigger"),
                PROVIDER,
                caller,
            ),
        ),
        (
            "discovery:CancelJobRun",
            f"{MODULE}job_run/default/research/ingest/ingest%3A7",
            "RUN_NOT_FOUND",
            lambda s, caller: s.authorize_job(
                pb.AuthorizeJobRequest(
                    **lease, job_name="ingest", operation="cancel", run_id="ingest:7"
                ),
                PROVIDER,
                caller,
            ),
        ),
    ]


def _callers(h: IAMHarness) -> dict[str, tuple[str, CallContext]]:
    """A recorded service account and an IAM user through api, both without a
    policy; their principal ids, and their verified contexts."""
    module = h.service_account("caller-module")
    user = h.user("bob")
    return {
        "service_account": (
            module.id,
            CallContext(principal=service_account("caller-module")),
        ),
        "user_via_api": (
            user.id,
            CallContext(
                principal=service_account("api"),
                on_behalf_of=Principal(id=user.id, kind="user"),
            ),
        ),
    }


@pytest.mark.parametrize("who", ["service_account", "user_via_api"])
def test_a_caller_without_a_policy_cannot_use_what_a_ready_module_serves(who):
    async def scenario():
        iam = contract_iam()
        h = IAMHarness(iam)
        service = DiscoveryService(MemoryRegistry(), iam=iam)
        req = await _ready(service)
        principal_id, caller = _callers(h)[who]
        for action, resource, not_found, use in _uses(req):
            # Without a policy the caller cannot even see it.
            with pytest.raises(DiscoveryError, match=not_found):
                await use(service, caller)
            # Granted, it may; denied explicitly, it may not.
            policy = h.grant(principal_id, statement("Allow", [action], [resource]))
            await use(service, caller)
            h.grant(
                principal_id,
                statement("Allow", ["discovery:*"], [resource]),
                statement("Deny", [action], [resource]),
            )
            # Still visible through another action of its type: denied; else
            # not found (a module's model has no other action).
            others = set(
                iam.catalogs.actions_on("discovery", parse_resource_name(resource).type)
            ) - {action}
            expected = PermissionDeniedError if others else DiscoveryError
            with pytest.raises(expected):
                await use(service, caller)
            del policy

    asyncio.run(scenario())


def test_an_app_is_told_who_the_verified_actor_is():
    """The app host hands the actor to the app: an app that authorizes more
    narrowly than OpenApp (the IdP's admin API) must not trust the user alone."""

    async def scenario():
        iam = contract_iam()
        h = IAMHarness(iam)
        service = DiscoveryService(MemoryRegistry(), iam=iam)
        req = await _ready(service)
        module = h.service_account("caller-module")
        # A workspace role gives the account platform viewer: OpenApp on every app.
        h.attach("builtin.platform.viewer", module.id)
        auth = pb.AuthorizeAppRequest(
            instance_id="instance", lease_token=req.lease_token, app_name="console"
        )
        answer = await service.authorize_app(
            auth, PROVIDER, CallContext(principal=service_account("caller-module"))
        )
        assert answer.caller_user_id == ""
        assert (
            answer.caller_principal_kind,
            answer.caller_principal_name,
        ) == ("service_account", "caller-module")
        # A user holds no policy of their own: a workspace role gives theirs.
        user = h.user("x")
        h.attach("builtin.platform.viewer", user.id)
        via_api = CallContext(
            principal=service_account("api"),
            on_behalf_of=Principal(id=user.id, kind="user"),
        )
        answer = await service.authorize_app(auth, PROVIDER, via_api)
        assert (answer.caller_user_id, answer.caller_principal_name) == (user.id, "api")

    asyncio.run(scenario())


def test_the_runs_a_user_starts_are_the_users():
    async def scenario():
        iam = contract_iam()
        h = IAMHarness(iam)
        service = DiscoveryService(MemoryRegistry(), iam=iam)
        req = await _ready(service)
        ada, bob = h.user("ada"), h.user("bob")
        for user in (ada, bob):
            h.attach("builtin.platform.member", user.id)

        def via_api(user):
            return CallContext(
                principal=service_account("api"),
                on_behalf_of=Principal(id=user.id, kind="user"),
            )

        lease: dict[str, Any] = {
            "instance_id": "instance",
            "lease_token": req.lease_token,
        }
        started = await service.authorize_agent(
            pb.AuthorizeAgentRequest(
                **lease, agent_name="Researcher", new_invocation=True
            ),
            PROVIDER,
            via_api(ada),
        )
        assert started.caller_identity == ada.id

        def poll(operation, owner):
            return pb.AuthorizeAgentRequest(
                **lease,
                agent_name="Researcher",
                operation=operation,
                invocation_id="run-1",
                run_owner=owner,
            )

        for operation in ("status", "event", "cancel"):
            mine = await service.authorize_agent(
                poll(operation, ada.id), PROVIDER, via_api(ada)
            )
            assert mine.run_authorized
            # Bob, through the same api, cannot see Ada's run.
            with pytest.raises(DiscoveryError, match="INVOCATION_NOT_FOUND"):
                await service.authorize_agent(
                    poll(operation, ada.id), PROVIDER, via_api(bob)
                )

    asyncio.run(scenario())


def test_members_and_modules_never_reach_each_others_runs():
    """Regression: a workspace member's role opens discovery, but never another
    principal's agent run."""

    async def scenario():
        iam = contract_iam()
        for nexus_id in ("user-aaaaaaaaaaaa", "user-bbbbbbbbbbbb"):
            with as_service_account("engine"):
                record = iam.ensure_user(LEGACY_NEXUS_ISSUER, nexus_id)
                iam.attach_policy("builtin.member", record.id, "abi:org-1:ws-1")
        service = DiscoveryService(MemoryRegistry(), iam=iam)
        req = await _ready(service)
        lease: dict[str, Any] = {
            "instance_id": "instance",
            "lease_token": req.lease_token,
        }

        def nexus(user_id: str) -> CallContext:
            return CallContext(
                principal=service_account("api"),
                on_behalf_of=Principal(id=user_id, kind="user"),
            )

        ada, bob = nexus("user-aaaaaaaaaaaa"), nexus("user-bbbbbbbbbbbb")
        module = CallContext(principal=service_account("other-module"))
        started = await service.authorize_agent(
            pb.AuthorizeAgentRequest(
                **lease, agent_name="Researcher", new_invocation=True
            ),
            PROVIDER,
            ada,
        )
        owner = started.caller_identity
        assert owner == "user-aaaaaaaaaaaa"
        for operation in ("status", "event", "cancel"):
            poll = pb.AuthorizeAgentRequest(
                **lease,
                agent_name="Researcher",
                operation=operation,
                invocation_id="run-1",
                run_owner=owner,
            )
            assert (await service.authorize_agent(poll, PROVIDER, ada)).run_authorized
            for stranger in (bob, module):
                with pytest.raises(DiscoveryError, match="INVOCATION_NOT_FOUND"):
                    await service.authorize_agent(poll, PROVIDER, stranger)

    asyncio.run(scenario())


def test_a_module_id_is_held_by_one_principal_at_a_time():
    async def scenario():
        service = DiscoveryService(MemoryRegistry(), iam=contract_iam())
        with as_service_account("engine"):
            await service.register(registration("research", "a"), "research")
            with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
                await service.register(registration("research", "b"), "intruder")
            # Its own replicas join it.
            await service.register(registration("research", "c"), "research")
            # A module account registers only its own module.
            with pytest.raises(DiscoveryError, match="PERMISSION_DENIED"):
                await service.register(
                    registration("other", "d"), "module/default/research"
                )
            await service.register(registration("mine", "e"), "module/default/mine")

    asyncio.run(scenario())


def test_registering_needs_the_callers_policy():
    async def scenario():
        iam = contract_iam()
        h = IAMHarness(iam)
        h.service_account("research")
        service = DiscoveryService(MemoryRegistry(), iam=iam)
        with (
            use_call_context(CallContext(principal=service_account("research"))),
            pytest.raises(DiscoveryError, match="PERMISSION_DENIED"),
        ):
            await service.register(registration("research", "a"), "research")

    asyncio.run(scenario())


def test_listing_shows_only_the_modules_and_agents_the_caller_may_list():
    async def scenario():
        iam = contract_iam()
        h = IAMHarness(iam)
        service = DiscoveryService(MemoryRegistry(), iam=iam)
        await _ready(service)
        bob = h.user()
        listing = pb.ListModulesRequest(limit=10)

        def as_bob():
            return h.as_(actor="api", on_behalf_of=bob)

        with as_bob():
            assert list((await service.list_modules(listing)).instances) == []
        h.grant(
            bob.id,
            statement(
                "Allow",
                ["discovery:ListModules"],
                [f"{MODULE}module/default/research"],
            ),
        )
        with as_bob():
            (instance,) = (await service.list_modules(listing)).instances
        assert instance.descriptor.module_id == "research"
        assert list(instance.descriptor.agents) == []  # no ListAgents
        h.attach("builtin.platform.viewer", bob.id)
        with as_bob():
            (instance,) = (await service.list_modules(listing)).instances
        assert [a.name for a in instance.descriptor.agents] == ["Researcher"]

    asyncio.run(scenario())


def test_a_caller_who_may_get_a_module_sees_its_instances():
    """GetModule is what reading one module needs: a module looking itself up
    (its bootstrap allows GetModule on its own module, not ListModules) sees
    its instances, each still showing only what it may list."""

    async def scenario():
        iam = contract_iam()
        h = IAMHarness(iam)
        service = DiscoveryService(MemoryRegistry(), iam=iam)
        await _ready(service)
        bob = h.user()
        get = pb.GetModuleRequest(module_id="research", contract_major=1)
        h.grant(
            bob.id,
            statement(
                "Allow",
                ["discovery:GetModule", "discovery:ListJobs"],
                [f"{MODULE}module/default/research", f"{MODULE}job/default/research/*"],
            ),
        )
        with h.as_(actor="api", on_behalf_of=bob):
            (instance,) = (await service.get_module(get)).instances
        assert instance.descriptor.module_id == "research"
        assert [j.name for j in instance.descriptor.jobs] == ["ingest"]
        assert list(instance.descriptor.agents) == []  # no ListAgents
        # Without GetModule the module is not found.
        eve = h.user("eve")
        with (
            h.as_(actor="api", on_behalf_of=eve),
            pytest.raises(DiscoveryError, match="MODULE_NOT_FOUND"),
        ):
            await service.get_module(get)

    asyncio.run(scenario())


def test_a_member_triggers_a_module_s_workflows_never_its_plain_jobs():
    """Members hold ``TriggerJob`` on ``workflow/*`` (the module scope tells
    workflows apart in Nexus), never on a plain job; a grant on ``job/…`` still
    covers a workflow, as a module's own manifest names its jobs."""

    async def scenario():
        iam = contract_iam()
        h = IAMHarness(iam)
        service = DiscoveryService(MemoryRegistry(), iam=iam)
        req = _provider()
        req.descriptor.jobs.add(
            name="sync",
            contract_major=1,
            kind="workflow",
            max_concurrency=1,
            max_attempts=1,
        )
        with as_service_account("engine"):
            await service.register(req, PROVIDER)
            await service.renew(
                pb.RenewRequest(
                    instance_id="instance",
                    lease_token=req.lease_token,
                    initialized=True,
                ),
                PROVIDER,
            )

        def trigger(job: str):
            return pb.AuthorizeJobRequest(
                instance_id="instance",
                lease_token=req.lease_token,
                job_name=job,
                operation="trigger",
            )

        member = h.user("member")
        h.attach("builtin.platform.member", member.id)
        caller = CallContext(
            principal=service_account("api"),
            on_behalf_of=Principal(id=member.id, kind="user"),
        )
        await service.authorize_job(trigger("sync"), PROVIDER, caller)
        with pytest.raises(DiscoveryError, match="JOB_NOT_FOUND"):
            await service.authorize_job(trigger("ingest"), PROVIDER, caller)

        viewer = h.user("viewer")
        h.attach("builtin.platform.viewer", viewer.id)
        as_viewer = CallContext(
            principal=service_account("api"),
            on_behalf_of=Principal(id=viewer.id, kind="user"),
        )
        with pytest.raises(DiscoveryError, match="JOB_NOT_FOUND"):
            await service.authorize_job(trigger("sync"), PROVIDER, as_viewer)

        module = h.service_account("caller-module")
        h.grant(
            module.id,
            statement(
                "Allow", ["discovery:TriggerJob"], [f"{MODULE}job/default/research/*"]
            ),
        )
        own = CallContext(principal=service_account("caller-module"))
        await service.authorize_job(trigger("sync"), PROVIDER, own)
        await service.authorize_job(trigger("ingest"), PROVIDER, own)

    asyncio.run(scenario())
