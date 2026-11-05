"""ExchangeRatesAPI agent: an SDK Agent hosted by the remote ``exchangeratesapi`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_apps.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
    ExchangeratesapiIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.agents import Agent

NAME = "ExchangeRatesAPI"
DESCRIPTION = (
    "Helps you interact with ExchangeRatesAPI for currency exchange rate information."
)
SYSTEM_PROMPT = """<role>
You are an ExchangeRatesAPI Agent with expertise in currency exchange rates and financial data.
</role>

<objective>
Help users access currency exchange rate information and understand exchange rate data.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Use your tools to retrieve latest or historical exchange rates and the list of currency symbols
- State the date and base currency of every rate you give
- If you have no tools, say so and ask the user to set the EXCHANGERATESAPI_API_KEY engine secret
</operating_guidelines>

<constraints>
- Do not make up exchange rates: only report rates returned by your tools
</constraints>
"""


def tools_for(credentials: dict[str, str]) -> list[Any]:
    """The ExchangeRatesAPI tools, or none without api_key."""
    if not all(credentials.get(field) for field in ("api_key",)):
        return []
    return as_tools(ExchangeratesapiIntegrationConfiguration(**credentials))


async def create_agent(
    engine: Any, module_id: str, *, credentials: dict[str, str], chat_model: str = ""
) -> Agent:
    tools = tools_for(credentials)
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        chat_model=chat_model,
    )
