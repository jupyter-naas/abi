from __future__ import annotations

import pytest
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.email.EmailPorts import EmailAttachment, IEmailAdapter
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class _DummyEmailAdapter(IEmailAdapter):
    def send(
        self,
        *,
        to_email: str | None = None,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        from_email: str,
        from_name: str | None = None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
        to_emails: list[str] | str | None = None,
        cc_emails: list[str] | str | None = None,
    ) -> None:
        return None


class _DummyEngine:
    def __init__(self, services: IEngine.Services) -> None:
        self.services = services
        self.modules: dict[str, object] = {}
        self.configuration = type("Cfg", (), {"default_agent": "core CoreAgent"})()


def test_engine_proxy_services_exposes_email_service():
    email_service = EmailService(_DummyEmailAdapter())
    engine = _DummyEngine(services=IEngine.Services(email=email_service))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[EmailService]),
    )

    assert proxy.services.email is email_service
    assert proxy.configuration.default_agent == "core CoreAgent"


def test_engine_proxy_services_denies_email_service_when_not_allowed():
    email_service = EmailService(_DummyEmailAdapter())
    engine = _DummyEngine(services=IEngine.Services(email=email_service))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[]),
    )

    with pytest.raises(ValueError, match="does not have access"):
        _ = proxy.services.email


def test_engine_proxy_grants_model_registry_without_declared_dependency():
    """ModelRegistryService is intentionally exempt from access control:
    the registry is a process-wide catalog, and any module can read or write
    to it (publish models, resolve defaults) without declaring it as a
    service dependency. See ``engine/context.py`` for the rationale."""
    registry = ModelRegistryService()
    engine = _DummyEngine(services=IEngine.Services(model_registry=registry))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[]),
    )

    assert proxy.services.model_registry_available() is True
    assert proxy.services.model_registry is registry


def test_engine_proxy_model_registry_available_false_when_engine_lacks_registry():
    """The availability check still honors engine-level absence — it's only
    the dependency-declaration gate that we dropped."""
    engine = _DummyEngine(services=IEngine.Services())

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[]),
    )

    assert proxy.services.model_registry_available() is False


def test_engine_proxy_services_exposes_dataset_service():
    from unittest.mock import MagicMock

    from naas_abi_core.services.dataset.DatasetService import DatasetService

    dataset_service = DatasetService(adapter=MagicMock())
    engine = _DummyEngine(services=IEngine.Services(dataset=dataset_service))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[DatasetService]),
    )

    assert proxy.services.dataset is dataset_service
    assert proxy.services.dataset_available() is True


def test_engine_proxy_services_denies_dataset_service_when_not_allowed():
    from unittest.mock import MagicMock

    from naas_abi_core.services.dataset.DatasetService import DatasetService

    dataset_service = DatasetService(adapter=MagicMock())
    engine = _DummyEngine(services=IEngine.Services(dataset=dataset_service))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[]),
    )

    assert proxy.services.dataset_available() is False
    with pytest.raises(ValueError, match="does not have access"):
        _ = proxy.services.dataset


def test_engine_proxy_services_exposes_document_service_scoped_to_module():
    from unittest.mock import MagicMock

    from naas_abi_core.services.document.DocumentPort import IDocumentAdapter
    from naas_abi_core.services.document.DocumentService import DocumentService

    root = DocumentService._for_engine(MagicMock(spec=IDocumentAdapter))
    engine = _DummyEngine(services=IEngine.Services(document=root))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[DocumentService]),
    )

    assert proxy.services.document_available() is True
    assert proxy.services.document.namespace == "test_module"


def test_engine_proxy_services_denies_document_service_when_not_allowed():
    from unittest.mock import MagicMock

    from naas_abi_core.services.document.DocumentPort import IDocumentAdapter
    from naas_abi_core.services.document.DocumentService import DocumentService

    root = DocumentService._for_engine(MagicMock(spec=IDocumentAdapter))
    engine = _DummyEngine(services=IEngine.Services(document=root))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[]),
    )

    assert proxy.services.document_available() is False
    with pytest.raises(ValueError, match="does not have access"):
        _ = proxy.services.document


def test_engine_proxy_document_view_is_cached_and_rebound_when_root_changes():
    """The scoped per-module DocumentService view is expensive to recreate
    (it binds a namespace), so it must be cached across repeated access and
    only rebuilt if the engine swaps in a different root document service."""
    from unittest.mock import MagicMock

    from naas_abi_core.services.document.DocumentPort import IDocumentAdapter
    from naas_abi_core.services.document.DocumentService import DocumentService

    root = DocumentService._for_engine(MagicMock(spec=IDocumentAdapter))
    engine = _DummyEngine(services=IEngine.Services(document=root))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[DocumentService]),
    )

    first = proxy.services.document
    assert proxy.services.document is first

    other_root = DocumentService._for_engine(MagicMock(spec=IDocumentAdapter))
    engine.services = IEngine.Services(document=other_root)

    second = proxy.services.document
    assert second is not first
    assert second.namespace == "test_module"


def test_engine_proxy_document_view_cache_is_thread_safe_under_contention():
    """Concurrent readers of the same unchanged root must be serialized by
    the cache lock so the expensive namespace-bound view is built once,
    with every caller observing the same cached instance afterward."""
    from threading import Barrier, Lock, Thread
    from time import sleep
    from unittest.mock import MagicMock, patch

    from naas_abi_core.services.document.DocumentPort import IDocumentAdapter
    from naas_abi_core.services.document.DocumentService import DocumentService

    root = DocumentService._for_engine(MagicMock(spec=IDocumentAdapter))
    engine = _DummyEngine(services=IEngine.Services(document=root))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[DocumentService]),
    )

    original = DocumentService._for_namespace
    call_count = 0
    count_lock = Lock()

    def slow_for_namespace(self, namespace):
        nonlocal call_count
        with count_lock:
            call_count += 1
        # Widens the race window a missing/broken lock would need to fail.
        sleep(0.05)
        return original(self, namespace)

    thread_count = 16
    barrier = Barrier(thread_count)
    results: list[DocumentService] = []
    errors: list[BaseException] = []
    results_lock = Lock()

    def access() -> None:
        try:
            barrier.wait(timeout=5)
            view = proxy.services.document
            with results_lock:
                results.append(view)
        except BaseException as exc:  # noqa: BLE001 - surfaced via errors below
            with results_lock:
                errors.append(exc)

    with patch.object(DocumentService, "_for_namespace", slow_for_namespace):
        threads = [Thread(target=access) for _ in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

    assert not errors
    assert len(results) == thread_count
    assert len({id(view) for view in results}) == 1
    assert call_count == 1
    assert results[0].namespace == "test_module"
