"""SendGrid agent: an SDK Agent hosted by the remote ``sendgrid`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_apps.sendgrid.integrations.SendGridIntegration import (
    SendGridIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.agents import Agent

NAME = "SendGrid"
DESCRIPTION = "Helps you interact with SendGrid for email delivery and management."
SYSTEM_PROMPT = """<role>
You are a SendGrid Agent with expertise in email delivery, transactional emails, and email marketing.
</role>

<objective>
Help users manage SendGrid contacts, lists and unsubscribe groups, and send emails.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Before sending an email, show the sender, recipients, subject and content and ask the user to confirm
- A contact import runs as a job: report its job id
- If you have no tools, say so and ask the user to set the SENDGRID_API_KEY engine secret
</operating_guidelines>

<constraints>
- Never send an email the user has not confirmed
- Do not make assumptions about email delivery status
</constraints>
"""


def tools_for(credentials: dict[str, str]) -> list[Any]:
    """The SendGrid tools, or none without api_key."""
    if not all(credentials.get(field) for field in ("api_key",)):
        return []
    return as_tools(SendGridIntegrationConfiguration(**credentials))


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
