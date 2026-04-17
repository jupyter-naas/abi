from __future__ import annotations

import pytest
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.email.EmailPorts import IEmailAdapter
from naas_abi_core.services.email.EmailService import EmailService


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
        self.modules: dict = {}


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
