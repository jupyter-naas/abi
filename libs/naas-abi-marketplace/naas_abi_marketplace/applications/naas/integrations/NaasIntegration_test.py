import pytest
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)


@pytest.fixture
def naas_integration() -> NaasIntegration:
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.naas import ABIModule

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.naas"])

    module = ABIModule.get_instance()
    naas_api_key = module.configuration.naas_api_key
    workspace_id = module.configuration.workspace_id
    storage_name = module.configuration.storage_name

    return NaasIntegration(
        NaasIntegrationConfiguration(
            api_key=naas_api_key,
            workspace_id=workspace_id,
            storage_name=storage_name,
        )
    )


def test_get_personal_workspace(naas_integration: NaasIntegration):
    result = naas_integration.get_personal_workspace()
    assert result is not None, f"No personal workspace found: {result}"
    return result


def test_list_workspaces(naas_integration: NaasIntegration):
    result = naas_integration.list_workspaces()
    assert len(result["workspaces"]) > 0, f"No workspaces found: {result}"


def test_list_plugins(naas_integration: NaasIntegration):
    workspace_id = naas_integration.get_personal_workspace()
    result = naas_integration.list_plugins(workspace_id)
    assert len(result["workspace_plugins"]) > 0, (
        f"No plugins found on personal workspace {workspace_id}: {result} "
    )


def test_list_ontologies(naas_integration: NaasIntegration):
    workspace_id = naas_integration.get_personal_workspace()
    result = naas_integration.list_ontologies(workspace_id)
    assert len(result["ontologies"]) > 0, (
        f"No ontologies found on personal workspace {workspace_id}: {result} "
    )


def test_list_secrets(naas_integration: NaasIntegration):
    result = naas_integration.list_secrets()
    assert len(result) > 0, result
