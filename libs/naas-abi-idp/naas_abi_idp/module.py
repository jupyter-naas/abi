"""The built-in identity provider as an SDK module.

``module_id`` is ``idp``: the module runs as the service account
``module/<project>/idp``, whose approved manifest (the default one for
``document``, ``secret`` and ``email``) reaches its own Document Service
namespace (``idp``), its own secrets (``idp/...``) and the engine's sender.
The engine seals both the namespace and the secrets to that account, so not
even ``api`` or ``engine`` reads them.

Two apps are announced to discovery: ``idp``, which Nexus serves at the issuer
URL on a dedicated route, and ``admin``, the JSON API of the provisioning port,
reached over NATS only.
"""

from __future__ import annotations

import asyncio
import logging

from naas_abi_sdk.apps import AppDescriptor
from naas_abi_sdk.module import BaseModule, ModuleDependencies

from naas_abi_idp.adapters.sdk import SdkDocumentStore, SdkMailer, SdkSecretStore
from naas_abi_idp.admin import AdminAPI
from naas_abi_idp.configuration import IdPConfiguration
from naas_abi_idp.service import IdPService
from naas_abi_idp.web import IdPWeb

log = logging.getLogger(__name__)

MODULE_ID = "idp"
# Expired requests, codes, sessions and counters go once in a while.
MAINTENANCE_SECONDS = 600
# Requests are small forms: nothing near the streaming threshold.
MAX_BODY_BYTES = 64 * 1024


class ABIModule(BaseModule[IdPConfiguration]):
    module_id = MODULE_ID
    Configuration = IdPConfiguration
    dependencies = ModuleDependencies(services=("document", "secret", "email"))
    apps = (
        AppDescriptor(
            name="idp",
            title="Identity provider",
            description="The built-in OIDC identity provider.",
            category="system",
            max_upload_bytes=MAX_BODY_BYTES,
        ),
        AppDescriptor(
            name="admin",
            title="Identity provider admin",
            description="Users, groups and clients of the built-in identity provider.",
            category="system",
            max_upload_bytes=MAX_BODY_BYTES,
        ),
    )

    service: IdPService

    async def on_initialized(self) -> None:
        config = self.configuration
        if not config.issuer:
            raise ValueError(
                "The identity provider needs its public issuer URL (issuer)"
            )
        loop = asyncio.get_running_loop()
        services = self.engine.services
        store = SdkDocumentStore(services.document, loop)
        secrets = SdkSecretStore(services.secret, loop)
        mailer = SdkMailer(services.email, loop)

        def build() -> IdPService:
            service = IdPService(store, secrets, mailer, config)
            service.seed_clients(config.clients)
            service.keys.active()  # the first signing key exists before the first request
            return service

        # The adapters wait on this loop: they must not run on it.
        self.service = await asyncio.to_thread(build)
        self.expose_app("idp", IdPWeb(self.service).app())
        self.expose_app("admin", AdminAPI(self.service).app())
        log.info("Identity provider ready at %s", config.issuer)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(MAINTENANCE_SECONDS)
            try:
                removed = await asyncio.to_thread(self.service.purge_expired)
                if removed:
                    log.debug("Removed %d expired identity records", removed)
            except Exception:
                log.exception("Identity maintenance failed")
