"""A job or workflow a first-party service starts for a user runs for that user.

The engine stores a delegation with the trigger of a module's job (the module
acting for the user, ``nats_broker_control``) and runs an engine module's job as
its job account for the user (``EngineJobLoader.job_authorizer``). A module's own
trigger hands no user on, as with agents.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import jwt
import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    current_call_context,
    service_account,
    use_call_context,
)
from naas_abi_core.engine.engine_loaders.EngineJobLoader import (
    as_engine,
    job_authorizer,
)
from naas_abi_core.engine.nats_broker_control import BrokerControl, Refused, _Request
from naas_abi_core.services.iam.modules import subject_token
from naas_abi_core.services.iam.tests.authorization_contract import contract_iam
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement

PEOPLE_JOBS = "abi:discovery:job/acme/people/*"
LEGACY_JOBS = "abi:discovery:job/acme/legacy/*"


def _world():
    iam = contract_iam()
    h = IAMHarness(iam)
    module = h.service_account("module/acme/people")
    bob, eve = h.user("bob"), h.user("eve")
    h.grant(
        bob.id, statement("Allow", ["discovery:TriggerJob"], [PEOPLE_JOBS, LEGACY_JOBS])
    )
    h.grant(module.id, statement("Allow", ["discovery:TriggerJob"], [LEGACY_JOBS]))
    api = iam.store.find_service_account("api")
    assert api is not None
    return iam, module, bob, eve, api


def _for(user, actor: Principal, scope=None) -> CallContext:
    return CallContext(
        principal=actor,
        on_behalf_of=Principal(id=user.id, kind="user") if user else None,
        scope=scope,
    )


def _api(record) -> Principal:
    return Principal(id=record.id, kind="service_account", name="api")


def _delegation(iam, context, *, trusted=True, module_id="people"):
    control = BrokerControl(iam, iam.verifier(), "nats://unused")
    request = _Request(control, context, None if trusted else SimpleNamespace())
    return control._delegation(request, "acme", module_id, "nightly")


def _claims(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


def test_a_trigger_nexus_stores_for_a_user_carries_the_modules_delegation():
    iam, module, bob, _, api = _world()
    scope = ({"effect": "Allow", "actions": ["discovery:*"], "resources": ["*"]},)

    token = _delegation(iam, _for(bob, _api(api), scope))

    claims = _claims(token)
    assert claims["aud"] == "abi:delegated:agent"
    assert claims["sub"] == bob.id
    # The job's module acts, for the user, within what the caller's credential allowed.
    assert claims["act"]["sub"] == module.id
    assert claims["abi_scope"] == list(scope)


def test_no_delegation_for_no_user_a_module_or_an_engine_job_and_a_refused_user_is_refused():
    iam, module, bob, eve, api = _world()
    as_module = Principal(id=module.id, kind="service_account", name=module.name)

    assert _delegation(iam, _for(None, _api(api))) is None
    # A user who may not start it: refused, never stored to run as the module alone.
    with pytest.raises(Refused, match="PERMISSION_DENIED|may not start"):
        _delegation(iam, _for(eve, _api(api)))
    # A module never hands a user to another module.
    assert _delegation(iam, _for(bob, as_module), trusted=False) is None
    # An engine module has no account of its own: the engine runs it for the user.
    assert _delegation(iam, _for(bob, _api(api)), module_id="legacy") is None


def _host_token(iam, caller: Principal, user) -> str:
    engine = iam.store.find_service_account("engine")
    assert engine is not None
    obo = Principal(id=user.id, kind="user") if user else None
    return iam.issue_host_token(caller, subject_token(engine.id), obo).token


def test_an_engine_job_triggered_for_a_user_runs_as_its_account_for_them():
    iam, module, bob, _, api = _world()
    authorize = job_authorizer(iam, iam.verifier(), "acme", "legacy", "job/legacy")

    def run_as(caller: Principal, user):
        headers = {"Nats-Auth-Token": _host_token(iam, caller, user)}
        return asyncio.run(authorize("trigger", "nightly", "nightly:1", headers, None))

    context = run_as(_api(api), bob)
    assert context.principal == service_account("job/legacy")
    assert context.on_behalf_of.id == bob.id

    seen = []

    async def handler(ctx):
        seen.append(current_call_context())

    with use_call_context(context):
        asyncio.run(as_engine(handler, "job/legacy")(None))
    asyncio.run(as_engine(handler, "job/legacy")(None))
    # For the user when the trigger was theirs; the account alone otherwise.
    assert [(c.principal.name, c.user and c.user.id) for c in seen] == [
        ("job/legacy", bob.id),
        ("job/legacy", None),
    ]

    # A module acting for the user, or no user: the job's account alone.
    as_module = Principal(id=module.id, kind="service_account", name=module.name)
    assert run_as(as_module, bob) is None
    assert run_as(_api(api), None) is None


def test_a_user_who_may_start_only_workflows_gets_a_delegation_never_none():
    """Members hold TriggerJob on ``workflow/*`` alone: a workflow started for
    one through ``api`` runs as the module for them, never as the module alone."""
    iam, _module, _bob, _eve, api = _world()
    h = IAMHarness(iam)
    member = h.user("member")
    h.grant(
        member.id,
        statement(
            "Allow",
            ["discovery:TriggerJob"],
            ["abi:discovery:workflow/acme/people/*"],
        ),
    )
    token = _delegation(iam, _for(member, _api(api)))
    assert token is not None and _claims(token)["sub"] == member.id


def test_a_deny_on_a_workflow_s_job_name_refuses_it_wherever_it_is_decided():
    """A policy written before workflows had a second name: Allow ``job/…/*``,
    Deny ``job/…/purge``. The Deny holds against ``workflow/*`` too."""
    from naas_abi_core.services.discovery.discovery_service import trigger_decision

    iam, _module, _bob, _eve, api = _world()
    h = IAMHarness(iam)
    member = h.user("member")
    h.grant(
        member.id,
        statement("Allow", ["discovery:TriggerJob"], ["abi:discovery:workflow/acme/*"]),
        statement("Deny", ["discovery:TriggerJob"], ["abi:discovery:job/acme/*/purge"]),
    )
    context = _for(member, _api(api))
    with use_call_context(context):
        assert (
            trigger_decision(iam.authorize, "acme", "people", "purge", workflow=True)[0]
            is False
        )
        assert trigger_decision(iam.authorize, "acme", "people", "sync", workflow=True)[
            0
        ]
        # A plain job the member was never granted.
        assert not trigger_decision(
            iam.authorize, "acme", "people", "sync", workflow=False
        )[0]

    # The broker control: refused, no delegation.
    control = BrokerControl(iam, iam.verifier(), "nats://unused")
    with pytest.raises(Refused):
        control._delegation(_Request(control, context, None), "acme", "people", "purge")

    # An engine module's host.
    authorize = job_authorizer(
        iam,
        iam.verifier(),
        "acme",
        "legacy",
        "job/legacy",
        frozenset({"purge", "sync"}),
    )

    def run_as(job: str):
        headers = {"Nats-Auth-Token": _host_token(iam, _api(api), member)}
        return asyncio.run(authorize("trigger", job, f"{job}:1", headers, None))

    with pytest.raises(Exception, match="PERMISSION_DENIED|JOB_NOT_FOUND|denied"):
        run_as("purge")
    assert run_as("sync").on_behalf_of.id == member.id
