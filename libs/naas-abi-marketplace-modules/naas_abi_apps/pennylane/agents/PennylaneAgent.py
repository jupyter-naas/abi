"""Pennylane agent: an SDK Agent hosted by the remote ``pennylane`` module.

Its chat model is the engine's, reached over NATS, and its memory is
checkpointed in the engine's Document Service. Nothing here imports
``naas_abi_core``.
"""

from __future__ import annotations

from typing import Any

from naas_abi_apps.pennylane.integrations.PennylaneIntegration import (
    PennylaneIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.agents import Agent, AgentConfiguration
from naas_abi_sdk.agents.hosting import agent_memory_id, document_memory

NAME = "Pennylane"
DESCRIPTION = "A Pennylane Agent for managing accounting and financial operations."
SYSTEM_PROMPT = """Tu es un agent Pennylane avec accès aux outils d'intégration Pennylane.
Si tu n'as pas accès aux outils, demande à l'utilisateur de configurer le secret PENNYLANE_API_KEY.
Sois toujours clair et professionnel dans ta communication en aidant les utilisateurs à gérer leurs données comptables.
Fournis toujours tout le contexte (réponse des outils, brouillon, etc.) à l'utilisateur dans ta réponse finale.
"""


def tools_for(
    api_key: str | None, *, datastore_path: str = "pennylane", storage: Any = None
) -> list[Any]:
    """The Pennylane tools, or none without an API key."""
    if not api_key:
        return []
    return as_tools(
        PennylaneIntegrationConfiguration(
            api_key=api_key, datastore_path=datastore_path, storage=storage
        )
    )


async def create_agent(
    engine: Any,
    module_id: str,
    *,
    api_key: str | None,
    datastore_path: str = "pennylane",
    chat_model: str = "",
) -> Agent:
    """``engine``: the module's ``self.engine`` (``model_registry``, ``document``
    and ``object_storage`` declared)."""
    registry = engine.services.model_registry
    chat = await (
        registry.get_chat_model(chat_model)
        if chat_model
        else registry.get_default_chat_model()
    )
    return Agent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=chat.model,
        tools=tools_for(
            api_key,
            datastore_path=datastore_path,
            storage=engine.services.object_storage,
        ),
        memory=await document_memory(
            engine.services.document, agent_memory_id(module_id, NAME)
        ),
        configuration=AgentConfiguration(system_prompt=SYSTEM_PROMPT),
    )
