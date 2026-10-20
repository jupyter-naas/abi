from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from jinja2 import Environment, StrictUndefined
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_DocumentService import (
    DocumentAdapterConfiguration,
    DocumentServiceConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.document.DocumentPort import (
    CollectionSpec,
    DocumentNotFound,
    IDocumentAdapter,
)
from naas_abi_core.services.document.DocumentService import DocumentService


def test_yaml_configuration_and_module_dependency_load_and_scope(tmp_path):
    configuration = EngineConfiguration.from_yaml_content(f"""
api: {{}}
global_config:
  ai_mode: local
modules: []
services:
  secret:
    secret_adapters: []
  document:
    document_adapter:
      adapter: sqlite
      config:
        path: {tmp_path / "documents.sqlite"}
""")
    dependencies = ModuleDependencies(modules=[], services=[DocumentService])
    services = EngineServiceLoader(configuration).load_services(
        {"my.module": dependencies}
    )
    assert services.document_available()
    assert services.document.services_wired
    engine = Mock(services=services)
    one = EngineProxy(engine, "one.module", dependencies).services
    two = EngineProxy(engine, "two.module", dependencies).services
    for proxy in (one, two):
        assert proxy.document_available()
        assert proxy.document is proxy.document
        assert proxy.document.services_wired
        assert proxy.document.services is services
        with pytest.raises(PermissionError, match="namespace"):
            proxy.document._for_namespace("unrelated.module")
        proxy.document.ensure_collection(CollectionSpec(name="records"))
    one.document.put("records", "id", {"owner": "one"})
    assert one.document.get("records", "id").data == {"owner": "one"}
    assert two.document.count("records") == 0
    with pytest.raises(DocumentNotFound):
        two.document.get("records", "id")
    denied = EngineProxy(
        engine, "denied", ModuleDependencies(modules=[], services=[])
    ).services
    assert not denied.document_available()
    with pytest.raises(ValueError, match="does not have access"):
        _ = denied.document


def test_service_is_not_loaded_without_dependency():
    configuration = Mock()
    services = EngineServiceLoader(configuration).load_services({})
    assert not services.document_available()
    configuration.services.document.load.assert_not_called()


def test_cached_proxy_tracks_root_replacement_and_still_checks_access():
    dependencies = ModuleDependencies(modules=[], services=[DocumentService])
    root = DocumentService._for_engine(Mock(spec=IDocumentAdapter))
    engine = Mock(services=Mock(document=root))
    proxy = EngineProxy(engine, "module", dependencies).services
    first = proxy.document
    engine.services.document = DocumentService._for_engine(Mock(spec=IDocumentAdapter))
    assert proxy.document is not first
    assert proxy.document.namespace == "module"
    dependencies.services = []
    with pytest.raises(ValueError, match="does not have access"):
        _ = proxy.document


def test_unavailable_backend_fails_at_service_loading():
    configuration = Mock()
    configuration.services.document.load.side_effect = ConnectionError("unavailable")
    with pytest.raises(ConnectionError, match="unavailable"):
        EngineServiceLoader(configuration).load_services(
            {"module": ModuleDependencies(modules=[], services=[DocumentService])}
        )


def test_proxy_availability_is_false_when_engine_has_no_document_service():
    proxy = EngineProxy(
        Mock(services=IEngine.Services()),
        "module",
        ModuleDependencies(modules=[], services=[DocumentService]),
    )
    assert not proxy.services.document_available()


@pytest.mark.parametrize(
    "config",
    [
        {"adapter": "postgresql", "config": {}},
        {
            "adapter": "postgresql",
            "config": {"dsn": "postgresql://example/test", "schema": "unsafe;sql"},
        },
        {"adapter": "sqlite", "config": {"timeout": -1}},
        {"adapter": "sqlite", "config": {"path": ""}},
        {"adapter": "sqlite", "config": {"unknown": True}},
        {"adapter": "unknown"},
        {"adapter": "custom"},
    ],
)
def test_invalid_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        DocumentAdapterConfiguration.model_validate(config)


def test_custom_adapter_uses_standard_loader(tmp_path):
    configuration = DocumentServiceConfiguration(
        document_adapter=DocumentAdapterConfiguration(
            adapter="custom",
            python_module="naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite",
            module_callable="DocumentSecondaryAdapterSQLite",
            custom_config={"path": str(tmp_path / "custom.sqlite")},
        )
    )
    adapter = configuration.document_adapter.load()
    try:
        assert isinstance(adapter, IDocumentAdapter)
    finally:
        adapter.close()


@pytest.mark.parametrize("scaffold", [False, True])
def test_remote_configuration_explicitly_uses_deployment_postgresql(scaffold):
    root = Path(__file__).resolve().parents[5]
    if scaffold:
        path = (
            root
            / "libs/naas-abi-cli/naas_abi_cli/cli/new/templates/project/config.remote.yaml"
        )
        content = (
            Environment(undefined=StrictUndefined, autoescape=False)  # nosec B701
            .from_string(path.read_text())
            .render(project_name_snake="example", project_name_pascal="Example")
        )
    else:
        content = (root / "config.remote.yaml").read_text()
    document = yaml.safe_load(content)["services"]["document"]
    configuration = DocumentServiceConfiguration.model_validate(document)
    assert configuration.document_adapter.adapter == "postgresql"
    dsn = configuration.document_adapter.config["dsn"]
    for secret in (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        assert "{{ secret." + secret + " }}" in dsn
