"""Ollama — local, keyless models for chat and embeddings.

This is the module that makes a fresh ABI project work with no API keys: it
serves both a chat model (Qwen2.5 3B) and an embedding model
(nomic-embed-text) from a locally running Ollama server, so the model registry
has real defaults without a single credential.

Unlike the cloud provider modules, "which endpoint" is a platform question
here — see ``endpoint.py`` for how macOS, Linux and Windows WSL are resolved.
"""

from typing import TYPE_CHECKING

from naas_abi_core.models.Model import ModelProvider
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.Logger import logger
from naas_abi_marketplace.ai.ollama.endpoint import (
    DEFAULT_BASE_URL,
    find_ollama_binary,
    install_hint,
    resolve_base_url,
)

if TYPE_CHECKING:
    from langchain_ollama import ChatOllama, OllamaEmbeddings


class ABIModule(BaseModule):
    name: str = "Ollama"
    description: str = (
        "Run open models locally with Ollama — chat and embeddings with no API "
        "keys, no cloud calls, and no data leaving the machine."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
    )
    tags: list[str] = ["ollama", "local", "open source", "offline", "privacy"]
    slug: str = "ollama"
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService, ModelRegistryService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.ai.ollama
        enabled: true
        config:
            # Optional — auto-detected when omitted (localhost, or the Windows
            # host when running under WSL). Also honours the ABI_OLLAMA_BASE_URL
            # and OLLAMA_HOST environment variables.
            base_url: "http://localhost:11434"
        """

        base_url: str | None = None
        # Probing costs one fast HTTP call on the happy path. Disable to skip
        # detection entirely and trust ``base_url`` as given.
        probe_on_load: bool = True
        datastore_path: str = "ollama"

    # Resolved during on_load, before model files are imported. Kept as a class
    # attribute so a directly-imported model file still finds a usable value.
    _resolved_base_url: str = DEFAULT_BASE_URL

    @property
    def base_url(self) -> str:
        """The Ollama endpoint this module talks to."""
        return self._resolved_base_url

    @classmethod
    def resolved_base_url(cls) -> str:
        """Endpoint for model files, which are imported during ``on_load``.

        Falls back to the platform default when the module has not been
        instantiated — importing a model file directly (in a unit test, say)
        must not blow up.
        """
        try:
            return cls.get_instance().base_url
        except ValueError:
            return cls._resolved_base_url

    def on_load(self):
        configured = self.configuration.base_url
        base_url, reachable = resolve_base_url(
            configured, probe=self.configuration.probe_on_load
        )
        # Assign on the class as well: model files reach this through
        # ``resolved_base_url()`` while ``super().on_load()`` imports them.
        self._resolved_base_url = base_url
        type(self)._resolved_base_url = base_url

        if reachable:
            logger.debug("Ollama: using %s", base_url)
        elif self.configuration.probe_on_load:
            # A warning, not an error: the project must still boot so the user
            # can fix ollama without ABI refusing to start.
            binary = find_ollama_binary()
            located = f" (binary found at {binary})" if binary else ""
            logger.warning(
                "Ollama: no server answered at %s%s. Local models will fail "
                "until one is running.\n%s",
                base_url,
                located,
                install_hint(),
            )

        # Registers everything under models/ (Qwen2.5 3B + nomic-embed-text).
        super().on_load()

        # Provider factories so *any* ollama model id works without a model
        # file — e.g. get_chat_model("qwen2.5:1.5b", provider="ollama") for a
        # lighter model on constrained hardware.
        #
        # langchain_ollama is imported inside the factories rather than at
        # module scope so that ``endpoint`` and ``defaults`` stay importable
        # without the ``ai-ollama`` extra — the Nexus API reads both, and it
        # does not depend on this module being enabled. Reaching here at all
        # means the module *is* enabled, so the extra is required and an
        # ImportError is the correct, and correctly-timed, failure.
        def ollama_chat_factory(provider_model_id: str) -> "ChatOllama":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=provider_model_id,
                base_url=base_url,
                temperature=0,
            )

        self.engine.services.model_registry.register_chat_provider(
            ModelProvider.OLLAMA, ollama_chat_factory
        )

        def ollama_embedding_factory(provider_model_id: str) -> "OllamaEmbeddings":
            from langchain_ollama import OllamaEmbeddings

            return OllamaEmbeddings(model=provider_model_id, base_url=base_url)

        self.engine.services.model_registry.register_embedding_provider(
            ModelProvider.OLLAMA, ollama_embedding_factory
        )
