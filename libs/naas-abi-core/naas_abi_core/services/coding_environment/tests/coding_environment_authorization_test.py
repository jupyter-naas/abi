"""Coding environments authorize every operation, in process and over NATS
alike; the owner and the user come from the call, never a request
field."""

from __future__ import annotations

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.coding_environment.adapters.primary.coding_environment__primary_adapter__NATS import (
    CodingEnvironmentPrimaryAdapterNATS,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient import (
    CodingEnvironmentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    WorkspaceNotFoundError,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from naas_abi_core.services.iam.tests.authorization_contract import (
    JWT_SECRET,
    AuthorizationContract,
    contract_iam,
    wire,
)
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement


class CodingEnvironmentContract(AuthorizationContract):
    NOT_FOUND = (WorkspaceNotFoundError,)

    @pytest.fixture
    def owner(self, contract_iam, tmp_path):
        return wire(CodingEnvironmentService(InMemoryAdapter()), contract_iam)

    @pytest.fixture(autouse=True)
    def _caller(self, caller):
        self.who = caller.id if caller.kind == "user" else (caller.name or caller.id)

    def primary(self, owner):
        return CodingEnvironmentPrimaryAdapterNATS(owner, JWT_SECRET)

    def facade(self, nats_url, identity):
        return CodingEnvironmentService(
            CodingEnvironmentSecondaryAdapterNATSClient(
                nats_url, TEST_TOKENS.source(identity)
            )
        )


class TestGetStatus(CodingEnvironmentContract):
    ACTION = "coding_environment:GetStatus"

    def prepare(self, owner):
        owner.ensure_user(email="engine@example.com", username="engine")
        self.env = owner.provision(template_id="tmpl-default", name="dev").id

    def resource(self, owner):
        return f"abi:-:-:coding_environment:environment/engine/{self.env}"

    def call(self, service):
        return service.get_status(workspace_id=self.env)


class TestProvision(CodingEnvironmentContract):
    ACTION = "coding_environment:Provision"

    def prepare(self, owner):
        # The caller's orchestrator user exists: provisioning is what is checked.
        owner.adapter.ensure_user(
            external_id=self.who, email="who@example.com", username="who"
        )

    def resource(self, owner):
        return f"abi:-:-:coding_environment:environment/{self.who}/-"

    def call(self, service):
        return service.provision(template_id="tmpl-default", name="dev")


def _service() -> tuple[CodingEnvironmentService, IAMHarness]:
    iam = contract_iam()
    return wire(CodingEnvironmentService(InMemoryAdapter()), iam), IAMHarness(iam)


def _own_environments(h: IAMHarness, principal_id: str) -> None:
    h.grant(
        principal_id,
        statement(
            "Allow",
            ["coding_environment:*"],
            [f"abi:*:*:coding_environment:environment/{principal_id}/*"],
        ),
    )


def test_an_environment_belongs_to_the_caller_whatever_the_request_names():
    ce, h = _service()
    alice, bob = h.user("alice"), h.user("bob")
    _own_environments(h, alice.id)
    _own_environments(h, bob.id)
    with h.as_(actor="api", on_behalf_of=bob):
        bob_user = ce.ensure_user(email="bob@example.com", username="bob")
        bob_env = ce.provision(template_id="tmpl-default", name="dev").id
    with h.as_(actor="api", on_behalf_of=alice):
        ce.ensure_user(email="alice@example.com", username="alice")
        # Naming bob's orchestrator user lists alice's, not bob's.
        assert ce.list_environments(user_id=bob_user) == []
        mine = ce.provision(template_id="tmpl-default", name="dev", user_id=bob_user)
        assert [e.id for e in ce.list_environments(user_id=bob_user)] == [mine.id]
        with pytest.raises(WorkspaceNotFoundError):
            ce.get_status(workspace_id=bob_env)
        with pytest.raises(WorkspaceNotFoundError):
            ce.get_access(workspace_id=bob_env, app_slug="code-server")


def test_an_environment_is_placed_in_the_target_workspace():
    ce, h = _service()
    h.admin("put_scope", "org-1", "ws-1")
    with use_call_context(
        CallContext(principal=service_account("engine"), workspace_id="ws-1")
    ):
        ce.ensure_user(email="e@example.com", username="engine")
        env = ce.provision(template_id="tmpl-default", name="dev")
    assert h.iam.resolve_placement("coding_environment", f"engine/{env.id}") == (
        "org-1",
        "ws-1",
    )


def test_listing_every_environment_is_an_admin_action():
    ce, h = _service()
    with as_service_account("engine"):
        ce.ensure_user(email="e@example.com", username="engine")
        ce.provision(template_id="tmpl-default", name="dev")
    bob = h.user("bob")
    _own_environments(h, bob.id)
    with h.as_(actor="api", on_behalf_of=bob):
        assert ce.list_all_environments() == []
    with as_service_account("engine"):
        assert len(ce.list_all_environments()) == 1
