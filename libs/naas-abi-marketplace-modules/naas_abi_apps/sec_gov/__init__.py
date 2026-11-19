"""SEC EDGAR: a remote ABI module (U.S. public company data).

Runs in its own process (``python -m naas_abi_apps.sec_gov``) and reaches the
engine only through NATS. Replaces the in-engine
``naas_abi_marketplace.applications.sec_gov``, which had no agent. This module
has none either: it publishes durable workflows other modules start by name,
``workflow.download_company_tickers_workflow`` and
``workflow.get_company_submissions_workflow``.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.sec_gov.integrations.SecGovIntegration import (
    TIMEOUT,
    SecGovIntegrationConfiguration,
)
from naas_abi_sdk import BaseModule, ModuleConfiguration, ModuleDependencies

MODULE_ID = "applications.sec_gov"


@dataclass
class SecGovConfiguration(ModuleConfiguration):
    # SEC EDGAR requires a descriptive User-Agent with a contact address.
    user_agent: str = "NAAS-ABI-Marketplace/1.0 (support@naas.ai)"
    # Object storage prefix the downloaded files are stored under.
    datastore_path: str = "sec_gov"


class ABIModule(BaseModule[SecGovConfiguration]):
    Configuration = SecGovConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    # document: durable workflows record their runs there.
    dependencies = ModuleDependencies(services=("document", "object_storage"))

    def integration_configuration(self) -> SecGovIntegrationConfiguration:
        return SecGovIntegrationConfiguration(
            user_agent=self.configuration.user_agent,
            datastore_path=self.configuration.datastore_path,
            storage=self.engine.services.object_storage,
            timeout=TIMEOUT,
        )

    async def run(self) -> None:
        await serve_until_stopped(self)
