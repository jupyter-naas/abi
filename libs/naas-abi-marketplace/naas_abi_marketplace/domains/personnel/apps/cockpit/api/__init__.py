"""Personnel Cockpit HTTP API — serves committed datasets from ``data/``."""

from naas_abi_marketplace.domains.personnel.apps.cockpit.api.routes import router

__all__ = ["router"]
