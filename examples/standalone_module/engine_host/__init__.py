"""Server-only composition module requesting the engine's complete service set."""

from naas_abi_core.engine.engine_loaders.EngineServiceLoader import (
    SERVICES_DEPENDENCIES,
)
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


class ABIModule(BaseModule):
    class Configuration(ModuleConfiguration):
        pass

    dependencies = ModuleDependencies(
        modules=[],
        services=[
            *SERVICES_DEPENDENCIES,
            ActivityLogService,
            CacheService,
            DatasetService,
            EmailService,
            KeyValueService,
            Secret,
            VectorStoreService,
        ],
    )
