from __future__ import annotations

import pytest
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.email.EmailPorts import IEmailAdapter
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class _DummyEmailAdapter(IEmailAdapter):
    def send(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        from_email: str,
        from_name: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        return None


class _DummyEngine:
    def __init__(self, services: IEngine.Services) -> None:
        self.services = services
        self.modules: dict[str, object] = {}


def test_engine_proxy_services_exposes_email_service():
    email_service = EmailService(_DummyEmailAdapter())
    engine = _DummyEngine(services=IEngine.Services(email=email_service))

    proxy = EngineProxy(
        engine=engine,
        module_name="test_module",
        module_dependencies=ModuleDependencies(modules=[], services=[EmailService]),
    )

    assert proxy.services.email is email_service


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
