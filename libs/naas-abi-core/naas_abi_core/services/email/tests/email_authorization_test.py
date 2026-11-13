"""Email authorizes every operation, in process and over NATS alike."""

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
from naas_abi_core.services.iam.tests.iam_harness import NEXUS, IAMHarness, statement

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
        return "abi:email:sender/noreply%40example.com"

    def call(self, service):
        return _send(service)


class TestGetSent(EmailContract):
    ACTION = "email:GetSent"
    NOT_FOUND = (SentEmailNotFound,)

    def prepare(self, owner):
        self.message_id = _send(owner)

    def resource(self, owner):
        return f"abi:email:message/{self.message_id}"

    def call(self, service):
        return service.get_sent(self.message_id)


def test_a_sent_message_is_placed_in_the_container_of_the_call(tmp_path):
    iam = contract_iam()
    iam._register_catalog(NEXUS)
    ws_1 = IAMHarness(iam).register("ws-1")
    email = wire(EmailService(FilesystemAdapter(directory=str(tmp_path))), iam)
    with use_call_context(
        CallContext(principal=service_account("engine"), container=ws_1)
    ):
        message_id = _send(email)
    assert iam.resolve_placement("email", message_id) == ws_1


def test_list_sent_returns_only_the_messages_the_caller_may_list(tmp_path):
    iam = contract_iam()
    h = IAMHarness(iam)
    email = wire(EmailService(FilesystemAdapter(directory=str(tmp_path))), iam)
    with as_service_account("engine"):
        first, second = _send(email, "first"), _send(email, "second")
    bob = h.user()
    h.grant(
        bob.id,
        statement("Allow", ["email:ListSent"], [f"abi:email:message/{second}"]),
    )
    with h.as_(actor="api", on_behalf_of=bob):
        assert [m.message_id for m in email.list_sent()] == [second]
    with as_service_account("engine"):
        assert {m.message_id for m in email.list_sent()} == {first, second}


def test_a_kept_copy_keeps_to_where_its_sender_may_send(tmp_path):
    from naas_abi_core.engine.call_context import Principal
    from naas_abi_core.services.iam.IAMPorts import (
        PermissionDeniedError,
        ResourceNotFoundError,
    )

    iam = contract_iam()
    iam._register_catalog(NEXUS)
    h = IAMHarness(iam)
    ws_a = h.register("ws-a", "org-a")
    email = wire(EmailService(FilesystemAdapter(directory=str(tmp_path))), iam)
    sender = "abi:email:sender/noreply%40example.com"
    # Allowed to send from the address only: nothing in ws-a.
    module = h.service_account("module-sender")
    h.grant(module.id, statement("Allow", ["email:Send"], [sender]))
    # Allowed to send from the address, and messages in ws-a.
    member = h.service_account("ws-a-sender")
    h.grant(member.id, statement("Allow", ["email:Send"], [sender, f"{ws_a}/*"]))
    reader = h.user("alice")
    h.grant(reader.id, statement("Allow", ["email:ListSent"], [f"{ws_a}/*"]))

    def as_account(record, container):
        return use_call_context(
            CallContext(
                principal=Principal(
                    id=record.id, kind="service_account", name=record.name
                ),
                container=container,
            )
        )

    with as_account(module, ws_a), pytest.raises(
        (PermissionDeniedError, ResourceNotFoundError)
    ):
        _send(email, "elsewhere")
    with as_service_account("engine"):
        assert [m.subject for m in email.list_sent()] == []  # nothing was sent

    with as_account(module, None):  # no container: kept, placed nowhere
        unplaced = _send(email, "platform")
    with as_account(member, ws_a):
        placed = _send(email, "ws-a")

    assert iam.resolve_placement("email", placed) == ws_a
    assert iam.placement_of("email", unplaced) is None
    with h.as_(reader):
        assert [m.subject for m in email.list_sent()] == ["ws-a"]
