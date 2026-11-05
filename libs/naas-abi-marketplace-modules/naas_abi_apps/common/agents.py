"""Build an application's agent the same way in every module: the engine's chat
(and, for intents, embedding) model, memory in the engine's Document Service."""

from __future__ import annotations

from typing import Any

from naas_abi_sdk.agents import Agent, AgentConfiguration, IntentAgent
from naas_abi_sdk.agents.hosting import agent_memory_id, document_memory


def tools_prompt(system_prompt: str, tools: list[Any], marker: str = "[TOOLS]") -> str:
    """Replace ``marker`` in the prompt with one ``- name: description`` line per tool."""
    lines = "\n".join(f"- {tool.name}: {tool.description}" for tool in tools)
    return system_prompt.replace(marker, lines)


async def build_agent(
    engine: Any,
    module_id: str,
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: list[Any] | None = None,
    intents: list[Any] | None = None,
    chat_model: str = "",
) -> Agent:
    """An ``IntentAgent`` when ``intents`` is given, else a plain ``Agent``.

    ``engine`` must declare ``model_registry`` and ``document``. ``chat_model``:
    a canonical model id the engine registers; empty for its default.
    """
    registry = engine.services.model_registry
    chat = await (
        registry.get_chat_model(chat_model)
        if chat_model
        else registry.get_default_chat_model()
    )
    memory = await document_memory(
        engine.services.document, agent_memory_id(module_id, name)
    )
    configuration = AgentConfiguration(system_prompt=system_prompt)
    if intents is None:
        return Agent(
            name=name,
            description=description,
            chat_model=chat.model,
            tools=tools or [],
            memory=memory,
            configuration=configuration,
        )
    embeddings = await registry.get_default_embedding_model()
    return IntentAgent(
        name=name,
        description=description,
        chat_model=chat.model,
        embedding_model=embeddings.model,
        tools=tools or [],
        intents=intents,
        memory=memory,
        configuration=configuration,
    )


async def read_secrets(engine: Any, names: dict[str, str]) -> dict[str, str]:
    """``{field: secret name}`` -> ``{field: value}``; a missing secret is ``""``.
    ``engine`` must declare ``secret``."""
    secrets = engine.services.secret
    values = {}
    for field, secret_name in names.items():
        values[field] = (
            (await secrets.get(secret_name, None) or "") if secret_name else ""
        )
    return values
