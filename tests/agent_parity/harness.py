"""Parity harness: one scenario, two agent runtimes.

``CoreRunner`` drives ``naas_abi_core``'s synchronous Agent; ``SdkRunner`` drives
``naas_abi_sdk.agents`` (async, core-free). Scenarios only talk to a runner, so the
same expectations hold both implementations to one behaviour.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
from collections.abc import Callable
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

Step = AIMessage | BaseException | Callable[[list[BaseMessage]], AIMessage]


class ScriptedChatModel(BaseChatModel):
    """Replays ``script`` (one entry per model call) and records every input.

    An entry is an AIMessage, an exception to raise, or a callable that builds the
    reply from the messages it received. The last entry repeats. ``bind_tools``
    returns ``self`` so the script survives tool binding.
    """

    script: list[Any]
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedChatModel:
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.received.append(list(messages))
        step = self.script[min(len(self.received) - 1, len(self.script) - 1)]
        if isinstance(step, BaseException):
            raise step
        message = step(messages) if callable(step) else step
        return ChatResult(generations=[ChatGeneration(message=message.model_copy())])


class TableEmbeddings(Embeddings):
    """Deterministic embeddings: ``table`` vectors for known texts, a stable
    pseudo-random unit vector (near-orthogonal to everything) otherwise."""

    def __init__(
        self,
        table: dict[str, list[float]] | None = None,
        dim: int = 64,
        fail: bool = False,
    ):
        self.table, self.dim, self.fail = dict(table or {}), dim, fail

    def _vector(self, text: str) -> list[float]:
        if self.fail:
            raise ConnectionError("embedding provider unreachable")
        if text in self.table:
            vector = list(self.table[text]) + [0.0] * (self.dim - len(self.table[text]))
        else:
            seed = hashlib.sha256(text.encode()).digest() * 2
            vector = [(b - 127.5) for b in seed[: self.dim]]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def _make(runner, cls, model, tools, system_prompt, thread_id, configuration, **kwargs):
    from langgraph.checkpoint.memory import InMemorySaver

    return cls(
        name="Parity",
        description="Parity test agent.",
        chat_model=model,
        tools=list(tools),
        memory=InMemorySaver(),
        state=runner.State(thread_id=thread_id),
        configuration=configuration
        or runner.Configuration(system_prompt=system_prompt),
        **kwargs,
    )


class CoreRunner:
    name = "core"

    def __init__(self) -> None:
        from naas_abi_core.services.agent.Agent import (
            Agent,
            AgentConfiguration,
            AgentSharedState,
        )
        from naas_abi_core.services.agent.beta.IntentMapper import Intent, IntentType
        from naas_abi_core.services.agent.IntentAgent import IntentAgent

        self.Agent, self.Configuration, self.State = (
            Agent,
            AgentConfiguration,
            AgentSharedState,
        )
        self.IntentAgent, self.Intent, self.IntentType = IntentAgent, Intent, IntentType

    def make(
        self,
        model,
        tools=(),
        *,
        system_prompt="You are Parity.",
        thread_id="t-1",
        agent_class=None,
        configuration=None,
        **kwargs,
    ):
        return _make(
            self,
            agent_class or self.Agent,
            model,
            tools,
            system_prompt,
            thread_id,
            configuration,
            **kwargs,
        )

    def make_intent(
        self,
        model,
        tools=(),
        *,
        system_prompt="You are Parity.",
        thread_id="t-1",
        configuration=None,
        **kwargs,
    ):
        return _make(
            self,
            self.IntentAgent,
            model,
            tools,
            system_prompt,
            thread_id,
            configuration,
            **kwargs,
        )

    def events(self, agent, prompt: str) -> list[dict[str, str]]:
        return list(agent.stream_invoke(prompt))

    def invoke(self, agent, prompt: str) -> str:
        return agent.invoke(prompt)

    def duplicate(self, agent, thread_id: str):
        return agent.duplicate(agent_shared_state=self.State(thread_id=thread_id))


class SdkRunner:
    name = "sdk"

    def __init__(self) -> None:
        from naas_abi_sdk.agents import (
            Agent,
            AgentConfiguration,
            AgentSharedState,
            Intent,
            IntentAgent,
            IntentType,
        )

        self.Agent, self.Configuration, self.State = (
            Agent,
            AgentConfiguration,
            AgentSharedState,
        )
        self.IntentAgent, self.Intent, self.IntentType = IntentAgent, Intent, IntentType

    def make(
        self,
        model,
        tools=(),
        *,
        system_prompt="You are Parity.",
        thread_id="t-1",
        agent_class=None,
        configuration=None,
        **kwargs,
    ):
        return _make(
            self,
            agent_class or self.Agent,
            model,
            tools,
            system_prompt,
            thread_id,
            configuration,
            **kwargs,
        )

    def make_intent(
        self,
        model,
        tools=(),
        *,
        system_prompt="You are Parity.",
        thread_id="t-1",
        configuration=None,
        **kwargs,
    ):
        return _make(
            self,
            self.IntentAgent,
            model,
            tools,
            system_prompt,
            thread_id,
            configuration,
            **kwargs,
        )

    def events(self, agent, prompt: str) -> list[dict[str, str]]:
        async def collect():
            return [event async for event in agent.stream_invoke(prompt)]

        return asyncio.run(collect())

    def invoke(self, agent, prompt: str) -> str:
        return asyncio.run(agent.invoke(prompt))

    def duplicate(self, agent, thread_id: str):
        return agent.duplicate(agent_shared_state=self.State(thread_id=thread_id))
