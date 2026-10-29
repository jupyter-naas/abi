"""Objects, listed for the policy builder as the caller (``services/iam/AGENTS.md``,
"Publishers and listing"): one check, IAM's, and an empty page for nothing."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.kernel_catalogs import kernel_catalogs, register_listers
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


@pytest.fixture
def warnings() -> Iterator[list[str]]:
    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    yield seen
    logger.remove(sink)


@pytest.fixture
def world(tmp_path):
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    with as_service_account("engine"):
        for catalog in kernel_catalogs():
            iam.register_catalog(catalog)
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
    storage.set_services(IEngine.Services(iam=iam))
    with as_service_account("engine"):
        storage.put_object("reports", "q3.pdf", b"q3")
        storage.put_object("drafts", "q4.pdf", b"q4")
    assert register_listers(iam, [storage]) == [("object_storage", "object")]
    return IAMHarness(iam)


def test_a_stranger_gets_an_empty_page_and_nothing_is_logged(world, warnings):
    stranger = world.user("stranger")
    with world.as_(stranger):
        page = world.iam.list_resources("object_storage", "object")
        searched = world.iam.list_resources("object_storage", "object", text="nowhere/")
    assert page.listed is True and page.items == ()
    assert searched.listed is True and searched.items == ()
    assert warnings == []


def test_a_reader_lists_what_they_may_list_and_under_a_prefix(world, warnings):
    reader = world.user("reader")
    world.grant(
        reader.id,
        statement("Allow", ["object_storage:ListObjects"], ["abi:object_storage:object/reports*"]),
    )
    with world.as_(reader):
        top = world.iam.list_resources("object_storage", "object")
        under = world.iam.list_resources("object_storage", "object", text="reports/")
    assert [i.id for i in top.items] == ["reports"]
    assert [i.id for i in under.items] == ["reports/q3.pdf"]
    assert warnings == []
