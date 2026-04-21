from typing import Optional

from langchain_core.tools import BaseTool, Tool, tool


def default_tools(self) -> list[Tool | BaseTool]:
    @tool(return_direct=False)
    def get_time_date(timezone: str = "Europe/Paris") -> str:
        """Returns the current date and time for a given timezone."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(timezone)).strftime("%H:%M:%S %Y-%m-%d")

    @tool(return_direct=True)
    def get_current_active_agent() -> str:
        """Returns the current active agent."""
        return "The current active agent is: " + (
            self._state.current_active_agent or self.name
        )

    @tool(return_direct=True)
    def get_supervisor_agent() -> str:
        """Returns the supervisor agent."""
        if self._state.supervisor_agent is None:
            return "I don't have a supervisor agent."
        return "The supervisor agent is: " + self._state.supervisor_agent

    @tool(return_direct=True)
    def list_tools_available() -> str:
        """Displays a formatted list of all available tools."""
        if not hasattr(self, "_structured_tools") or len(self._structured_tools) == 0:
            return "I don't have any tools available to help you at the moment."

        tools_text = "Here are the tools I can use to help you:\n\n"
        for t in self._structured_tools:
            if not t.name.startswith("transfer_to"):
                tools_text += f"- `{t.name}`: {t.description.splitlines()[0]}\n"
        return tools_text.rstrip()

    @tool(return_direct=True)
    def list_subagents_available() -> str:
        """Displays a formatted list of all available sub-agents."""
        if not hasattr(self, "_agents") or len(self._agents) == 0:
            return "I don't have any sub-agents that can assist me at the moment."

        agents_text = "I can collaborate with these sub-agents:\n"
        for agent in self._agents:
            agents_text += f"- `{agent.name}`: {agent.description}\n"
        return agents_text.rstrip()

    @tool(return_direct=True)
    def list_intents_available() -> str:
        """Displays a formatted list of all available intents."""
        if not hasattr(self, "_intents") or len(self._intents) == 0:
            return "I haven't been configured with any specific intents yet."

        from ..beta.IntentMapper import (
            Intent,
            IntentScope,
            IntentType,
        )

        # Group intents by scope and type
        intents_by_scope: dict[
            Optional[IntentScope], dict[IntentType, list[Intent]]
        ] = {}
        for intent in self._intents:
            if intent.intent_scope not in intents_by_scope:
                intents_by_scope[intent.intent_scope] = {}
            if intent.intent_type not in intents_by_scope[intent.intent_scope]:
                intents_by_scope[intent.intent_scope][intent.intent_type] = []
            intents_by_scope[intent.intent_scope][intent.intent_type].append(intent)

        intents_text = "Here are all the intents I'm configured with:\n\n"
        for scope, types_dict in intents_by_scope.items():
            intents_text += f"### Intents for {str(scope)}\n\n"
            for intent_type, intents in types_dict.items():
                intents_text += f"#### {str(intent_type)}\n\n"
                intents_text += "| Intent | Target |\n"
                intents_text += "|--------|--------|\n"
                for intent in intents:
                    if intent.intent_scope == IntentType.RAW:
                        intents_text += (
                            f"| {intent.intent_value} | {intent.intent_target} |\n"
                        )
                    else:
                        intents_text += (
                            f"| {intent.intent_value} | `{intent.intent_target}` |\n"
                        )
                intents_text += "\n"
        return intents_text.rstrip()

    tools: list[Tool | BaseTool] = [
        get_time_date,
        list_tools_available,
        list_subagents_available,
        list_intents_available,
    ]
    if self.state.supervisor_agent is not None or len(self._agents) > 0:
        tools.append(get_current_active_agent)
        tools.append(get_supervisor_agent)
    return tools
