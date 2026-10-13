"""{{agent_name_pascal}}: an SDK IntentAgent hosted by this remote module.

Its chat and embedding models are the engine's, reached over NATS, and its
conversation memory is checkpointed in the engine's Document Service, so it
survives restarts and is shared by replicas. Nothing here imports
``naas_abi_core``.

To publish it, declare it in ``ABIModule`` and bind it in ``on_initialized``:

    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=("agent.invoke.v1",)),)
    ...
    agent = await create_agent(self.engine, MODULE_ID)
    self.expose_agent(NAME, agent.as_handler())
"""

from __future__ import annotations

from typing import Any

from naas_abi_sdk.agents import AgentConfiguration, IntentAgent
from naas_abi_sdk.agents.hosting import agent_memory_id, document_memory

NAME = "{{agent_name_pascal}}"
DESCRIPTION = "A helpful agent that can help you with your tasks."
SYSTEM_PROMPT = """<role>
You are {{agent_name_pascal}}, a helpful assistant.
</role>

<objective>
Help the user accomplish their tasks using the tools available to you.
</objective>

<constraints>
- Answer briefly and factually.
- Say so when you do not know.
</constraints>
"""


async def create_agent(engine: Any, module_id: str, *, chat_model: str = "") -> IntentAgent:
    """``engine``: the module's ``self.engine``; it must declare the
    ``model_registry`` and ``document`` services. ``chat_model``: a canonical
    model id the engine registers, or empty for its default."""
    registry = engine.services.model_registry
    chat = await (
        registry.get_chat_model(chat_model)
        if chat_model
        else registry.get_default_chat_model()
    )
    embeddings = await registry.get_default_embedding_model()
    return IntentAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=chat.model,
        embedding_model=embeddings.model,
        # Keyed by module and agent, so a renamed module starts a new memory.
        memory=await document_memory(
            engine.services.document, agent_memory_id(module_id, NAME)
        ),
        configuration=AgentConfiguration(system_prompt=SYSTEM_PROMPT),
    )
