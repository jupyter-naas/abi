"""A chat model that replays a script: the LLM stand-in for turn-level tests.

``ScriptedChatModel`` answers each model call with the next message of the
script (the last one repeats) and records, per call, the tool names it was
bound with and the messages it received. ``bind_tools`` returns a copy that
shares the recorder, so the recording covers every binding an agent makes.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptRecorder:
    def __init__(self, script: list[AIMessage]):
        self.script = script
        self.bound: list[list[str]] = []
        self.seen: list[list[BaseMessage]] = []

    def tool_messages(self, call: int = -1) -> list[ToolMessage]:
        return [m for m in self.seen[call] if isinstance(m, ToolMessage)]


class ScriptedChatModel(BaseChatModel):
    recorder: Any
    bound_names: list[str] = []

    @classmethod
    def from_script(cls, script: list[AIMessage]) -> ScriptedChatModel:
        return cls(recorder=ScriptRecorder(script))

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedChatModel:
        names = [t["name"] if isinstance(t, dict) else t.name for t in tools]
        return self.model_copy(update={"bound_names": names})

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ) -> ChatResult:
        recorder: ScriptRecorder = self.recorder
        index = min(len(recorder.bound), len(recorder.script) - 1)
        recorder.bound.append(sorted(self.bound_names))
        recorder.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=recorder.script[index])])


def tool_call(name: str, args: dict[str, Any], id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id}])


def tool_calls(*calls: tuple[str, dict[str, Any], str]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": n, "args": a, "id": i} for n, a, i in calls],
    )
