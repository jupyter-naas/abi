"""Financial Cockpit — a finance & "pilotage" dashboard app template.

Ships a self-contained Next.js app (``apps/financial-cockpit/web``) with bundled
demo data, password-only local login (no e-mail service), and a hexagonal
FS<->R2 storage boundary so the same UI runs locally off ``web/data`` and in
production off a Cloudflare R2 bucket. Clone it and build your own finance app.

See ``apps/financial-cockpit/README.md`` for the quickstart.
"""

from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)


class ABIModule(BaseModule):
    """Registers the Financial Cockpit template with the ABI engine.

    The web app is a standalone dev/deploy artifact launched from its Makefile
    (``make dev``); this module only carries the catalog configuration (demo
    credentials + optional R2 target) so the app can be listed and, later,
    seeded to production.
    """

    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[])

    class Configuration(ModuleConfiguration):
        """
        module: naas_abi_marketplace.alpha.financial_cockpit
        enabled: true
        config:
            demo_login: "demo@financial-cockpit.local"
            demo_password: "demo"
            r2_account_id: "{{ secret.R2_ACCOUNT_ID }}"
            r2_access_key_id: "{{ secret.R2_ACCESS_KEY_ID }}"
            r2_secret_access_key: "{{ secret.R2_SECRET_ACCESS_KEY }}"
            r2_bucket: "app-financial-cockpit"
        """

        demo_login: str = "demo@financial-cockpit.local"
        demo_password: str = "demo"
        r2_account_id: str = ""
        r2_access_key_id: str = ""
        r2_secret_access_key: str = ""
        r2_bucket: str = "app-financial-cockpit"
