import asyncio
import dataclasses

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
    InMemoryResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AuditRecord,
    AuditUnavailable,
    ConfirmationRequired,
    ResourceTooLarge,
    UnknownService,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import (
    ResourceAdminService,
)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def objects():
    return InMemoryResources("object_storage", {"docs/a.txt": b"hello", "b.bin": b"\x00\x01"})


@pytest.fixture
def secrets():
    return InMemoryResources("secret", {"OPENAI_API_KEY": b"sk-123"}, masked=True)


@pytest.fixture
def audit():
    return InMemoryAuditLog()


@pytest.fixture
def admin(objects, secrets, audit):
    return ResourceAdminService(
        {
            "object_storage": objects,
            "secret": secrets,
            "cache": SourceUnavailable("cache", "no cache configured"),
        },
        audit,
        upload_limit=16,
        download_limit=4,
    )


def test_services_report_availability_and_capabilities(admin):
    services = {s.name: s for s in admin.services()}

    assert [s.name for s in admin.services()] == ["cache", "object_storage", "secret"]
    assert services["object_storage"].available and services["object_storage"].capabilities.browse
    assert services["secret"].capabilities.reveal is True
    assert (services["cache"].available, services["cache"].reason) == (False, "no cache configured")


def test_unknown_and_unavailable_services(admin):
    with pytest.raises(UnknownService):
        run(admin.list("nope"))
    with pytest.raises(SourceUnavailable) as exc:
        run(admin.list("cache"))
    assert exc.value.reason == "no cache configured"


def test_reading_never_reveals_and_is_not_audited(admin, audit):
    detail = run(admin.read("secret", "OPENAI_API_KEY"))

    assert detail.content.encoding == "masked"
    assert "sk-123" not in repr(detail)
    assert audit.records == []


def test_reveal_is_audited_before_and_after(admin, audit):
    detail = run(admin.reveal("u1", "secret", "OPENAI_API_KEY"))

    assert detail.content.text == "sk-123"
    action = AdminAction("u1", "secret", "reveal", "OPENAI_API_KEY")
    assert audit.records == [AuditRecord(action, "requested"), AuditRecord(action, "succeeded")]


def test_reveal_needs_a_masking_service(admin):
    with pytest.raises(UnsupportedOperation):
        run(admin.reveal("u1", "object_storage", "docs/a.txt"))


def test_creating_needs_no_confirmation(admin, objects, audit):
    entry = run(admin.write("u1", "object_storage", "docs/new.txt", b"fresh"))

    assert entry.id == "docs/new.txt"
    assert objects.items["docs/new.txt"] == b"fresh"
    assert [r.action.operation for r in audit.records] == ["create", "create"]


def test_replacing_needs_the_id_typed_back(admin, objects, audit):
    with pytest.raises(ConfirmationRequired) as exc:
        run(admin.write("u1", "object_storage", "docs/a.txt", b"changed"))
    assert exc.value.operation == "replace"
    assert objects.items["docs/a.txt"] == b"hello"
    assert audit.records == []

    run(admin.write("u1", "object_storage", "docs/a.txt", b"changed", confirm="docs/a.txt"))

    assert objects.items["docs/a.txt"] == b"changed"
    assert [(r.action.operation, r.phase) for r in audit.records] == [
        ("replace", "requested"),
        ("replace", "succeeded"),
    ]


def test_delete_needs_the_id_typed_back(admin, secrets, audit):
    with pytest.raises(ConfirmationRequired):
        run(admin.delete("u1", "secret", "OPENAI_API_KEY", confirm="openai_api_key"))
    assert "OPENAI_API_KEY" in secrets.items

    run(admin.delete("u1", "secret", "OPENAI_API_KEY", confirm="OPENAI_API_KEY"))

    assert "OPENAI_API_KEY" not in secrets.items
    assert audit.records[-1] == AuditRecord(
        AdminAction("u1", "secret", "delete", "OPENAI_API_KEY"), "succeeded"
    )


def test_no_change_without_an_audit_record(objects, secrets):
    admin = ResourceAdminService(
        {"object_storage": objects, "secret": secrets}, InMemoryAuditLog(fail="db down")
    )

    with pytest.raises(AuditUnavailable):
        run(admin.delete("u1", "object_storage", "b.bin", confirm="b.bin"))
    with pytest.raises(AuditUnavailable):
        run(admin.reveal("u1", "secret", "OPENAI_API_KEY"))

    assert "b.bin" in objects.items


def test_a_failed_change_is_audited_as_failed(admin, objects, audit):
    async def broken(resource_id):
        raise RuntimeError("storage exploded")

    objects.delete = broken

    with pytest.raises(RuntimeError):
        run(admin.delete("u1", "object_storage", "b.bin", confirm="b.bin"))

    assert audit.records[-1].phase == "failed"
    assert audit.records[-1].error == "RuntimeError"


def test_uploads_and_downloads_are_bounded(admin):
    with pytest.raises(ResourceTooLarge):
        run(admin.write("u1", "object_storage", "big.bin", b"x" * 17))
    with pytest.raises(ResourceTooLarge):
        run(admin.download("object_storage", "docs/a.txt"))

    entry, data = run(admin.download("object_storage", "b.bin"))
    assert (entry.id, data) == ("b.bin", b"\x00\x01")


def test_masked_values_cannot_be_downloaded(admin):
    with pytest.raises(UnsupportedOperation):
        run(admin.download("secret", "OPENAI_API_KEY"))


def test_an_expiry_reaches_only_services_that_support_it(objects, audit):
    class Expiring(InMemoryResources):
        def __init__(self):
            super().__init__("keyvalue")
            self.capabilities = dataclasses.replace(self.capabilities, expiry=True)
            self.ttls = {}

        async def write(self, resource_id, content, *, ttl_seconds=None):
            self.ttls[resource_id] = ttl_seconds
            return await super().write(resource_id, content)

    keyvalue = Expiring()
    service = ResourceAdminService({"object_storage": objects, "keyvalue": keyvalue}, audit)

    run(service.write("u1", "keyvalue", "k", b"v", ttl_seconds=60))
    run(service.write("u1", "keyvalue", "plain", b"v"))
    assert keyvalue.ttls == {"k": 60, "plain": None}
    with pytest.raises(UnsupportedOperation):
        run(service.write("u1", "object_storage", "c.txt", b"v", ttl_seconds=60))
    assert "c.txt" not in objects.items
