import os

from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from pydantic import Field

# Set to "1" by whoever starts the engine on their own checkout (ABI's
# `make commit`, `make push`, `make pr`, `make pull-request-description`):
# the same as `single_user_development: true` in the module's configuration.
SINGLE_USER_DEVELOPMENT_ENV = "ABI_GIT_SINGLE_USER_DEVELOPMENT"


def _single_user_development_from_env() -> bool:
    return os.environ.get(SINGLE_USER_DEVELOPMENT_ENV) == "1"


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService, Secret],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.git
        enabled: true
        config:
            datastore_path: "git"
            single_user_development: true
        """

        datastore_path: str = "git"

        # The Git agents run git, make and gh in the engine's own working
        # directory, with the engine's credentials. That is a developer's
        # checkout, never a shared deployment: they are module agents, and carry
        # their tools, only when this is set (here, or with
        # ABI_GIT_SINGLE_USER_DEVELOPMENT=1 in the engine's environment).
        single_user_development: bool = Field(
            default_factory=_single_user_development_from_env
        )


def acts_on_this_checkout() -> bool:
    """Whether the Git agents may act on the engine's working directory: the
    module is loaded and its configuration sets ``single_user_development``."""
    try:
        module = ABIModule.get_instance()
    except Exception:  # noqa: BLE001 - not loaded: nothing may act
        return False
    configuration = getattr(module, "configuration", None)
    return getattr(configuration, "single_user_development", False) is True
