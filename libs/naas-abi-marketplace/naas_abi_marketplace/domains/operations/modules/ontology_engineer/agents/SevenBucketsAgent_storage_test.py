"""save_ontology writes to the caller's own storage, never to the module's
shipped ontologies that the module loads at boot and the prompt quotes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import naas_abi_marketplace.domains.operations.modules.ontology_engineer as oe
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from naas_abi_core.engine.call_context import (
    CallContext,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from naas_abi_marketplace.domains.operations.modules.ontology_engineer.agents import (
    SevenBucketsAgent as sb,
)

PLANTED = "planted-into-the-template"
TURTLE = (
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
    f'<urn:x:note> rdfs:comment "{PLANTED}" .\n'
)


def digests(folder: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.glob("*"))
        if p.is_file()
    }


@pytest.fixture
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = ObjectStorageFactory.ObjectStorageServiceFS(str(tmp_path / "storage"))
    chat = FakeMessagesListChatModel(responses=[AIMessage(content="ok")])
    module = SimpleNamespace(
        configuration=oe.ABIModule.Configuration.model_construct(),
        engine=SimpleNamespace(
            services=SimpleNamespace(
                model_registry=SimpleNamespace(get_chat_model=lambda *a, **k: chat),
                object_storage=store,
            )
        ),
    )
    monkeypatch.setattr(oe.ABIModule, "get_instance", classmethod(lambda cls: module))
    return store


def save(**arguments: object) -> str:
    tools = {t.name: t for t in sb.create_agent().tools if hasattr(t, "name")}
    return str(tools["save_ontology"].invoke(arguments))


def test_save_ontology_keeps_shipped_ontologies_and_writes_the_callers_storage(
    storage,
) -> None:
    shipped = digests(sb._ONTOLOGIES_DIR)

    with use_call_context(CallContext(principal=user("usr-alice"))):
        out = save(filename=sb.TEMPLATE_ONTOLOGY.name, turtle=TURTLE, overwrite=True)

    assert digests(sb._ONTOLOGIES_DIR) == shipped
    prefix = "users/usr-alice/ontology-engineer/ontologies"
    assert f"{prefix}/{sb.TEMPLATE_ONTOLOGY.name}" in out
    assert PLANTED in storage.get_object(prefix, sb.TEMPLATE_ONTOLOGY.name).decode()
    prompt = sb.create_agent().configuration.system_prompt
    assert PLANTED not in prompt


def test_save_ontology_keeps_an_existing_file_unless_asked(storage) -> None:
    with use_call_context(CallContext(principal=user("usr-alice"))):
        save(filename="mine", turtle=TURTLE)
        again = save(filename="mine", turtle=TURTLE)

    assert again.startswith("File already exists")


def test_save_ontology_needs_a_user(storage, tmp_path: Path) -> None:
    out = save(filename="mine", turtle=TURTLE)
    with use_call_context(CallContext(principal=service_account("api"))):
        as_service = save(filename="mine", turtle=TURTLE)
    with use_call_context(
        CallContext(principal=service_account("api"), on_behalf_of=user("usr-bob"))
    ):
        for_bob = save(filename="for-bob", turtle=TURTLE)

    assert "signed-in user" in out
    assert "signed-in user" in as_service
    assert "users/usr-bob/" in for_bob
    written = [p for p in (tmp_path / "storage").rglob("*") if p.is_file()]
    assert all("usr-bob" in str(p) for p in written) and written
