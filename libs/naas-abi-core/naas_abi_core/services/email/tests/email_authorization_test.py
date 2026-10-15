"""Email authorizes every operation, in process and over NATS alike (RFC §6.4)."""

from __future__ import annotations

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.email.adapters.primary.email__primary_adapter__NATS import (
    EmailPrimaryAdapterNATS,
)
from naas_abi_core.services.email.adapters.secondary.EmailSecondaryAdapterNATSClient import (
    EmailSecondaryAdapterNATSClient,
)
from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
    FilesystemAdapter,
)
from naas_abi_core.services.email.EmailPorts import SentEmailNotFound
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.iam.tests.authorization_contract import (
    JWT_SECRET,
    AuthorizationContract,
    contract_iam,
    wire,
)
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement

SENDER = "noreply@example.com"


def _send(service: EmailService, subject: str = "Hello") -> str | None:
    return service.send(
        to_email="alice@example.com",
        subject=subject,
        text_body="Hello",
        from_email=SENDER,
    )


class EmailContract(AuthorizationContract):
    @pytest.fixture
    def owner(self, contract_iam, tmp_path):
        return wire(
            EmailService(FilesystemAdapter(directory=str(tmp_path))), contract_iam
        )

    def primary(self, owner):
        return EmailPrimaryAdapterNATS(owner, JWT_SECRET)

    def facade(self, nats_url, identity):
        return EmailService(
            EmailSecondaryAdapterNATSClient(nats_url, TEST_TOKENS.source(identity))
        )


class TestSend(EmailContract):
    ACTION = "email:Send"

    def resource(self, owner):
        return "abi:-:-:email:sender/noreply%40example.com"

    def call(self, service):
        return _send(service)


class TestGetSent(EmailContract):
    ACTION = "email:GetSent"
    NOT_FOUND = (SentEmailNotFound,)

    def prepare(self, owner):
        self.message_id = _send(owner)

    def resource(self, owner):
        return f"abi:-:-:email:message/{self.message_id}"

    def call(self, service):
        return service.get_sent(self.message_id)


def test_a_sent_message_is_placed_in_the_target_workspace(tmp_path):
    iam = contract_iam()
    h = IAMHarness(iam)
    h.admin("put_scope", "org-1", "ws-1")
    email = wire(EmailService(FilesystemAdapter(directory=str(tmp_path))), iam)
    with use_call_context(
        CallContext(principal=service_account("engine"), workspace_id="ws-1")
    ):
        message_id = _send(email)
    assert iam.resolve_placement("email", message_id) == ("org-1", "ws-1")


def test_list_sent_returns_only_the_messages_the_caller_may_list(tmp_path):
    iam = contract_iam()
    h = IAMHarness(iam)
    email = wire(EmailService(FilesystemAdapter(directory=str(tmp_path))), iam)
    with as_service_account("engine"):
        first, second = _send(email, "first"), _send(email, "second")
    bob = h.user()
    h.grant(
        bob.id,
        statement("Allow", ["email:ListSent"], [f"abi:-:-:email:message/{second}"]),
    )
    with h.as_(actor="api", on_behalf_of=bob):
        assert [m.message_id for m in email.list_sent()] == [second]
    with as_service_account("engine"):
        assert {m.message_id for m in email.list_sent()} == {first, second}
