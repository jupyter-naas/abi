from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class SendGridAgent(IntentAgent):
    name: str = "SendGrid"
    description: str = "Helps you interact with SendGrid for email delivery and management."
    system_prompt: str = """<role>
You are a SendGrid Agent with expertise in email delivery, transactional emails, and email marketing.
</role>

<objective>
Help users understand SendGrid capabilities and manage email delivery operations.
</objective>

<context>
You currently do not have access to SendGrid tools. You can only provide general information and guidance about SendGrid services and email delivery.
</context>

<tasks>
- Provide information about SendGrid email services
- Explain email delivery best practices
- Guide users on SendGrid features and capabilities
</tasks>

<operating_guidelines>
- Provide clear, accurate information about email delivery
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or send emails without tools
- Only provide general information and guidance
- Do not make assumptions about email delivery status
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "SendGridAgent":
        from naas_abi_marketplace.applications.sendgrid import ABIModule
        from naas_abi_marketplace.applications.sendgrid.integrations.SendGridIntegration import (
            SendGridIntegrationConfiguration,
            as_tools,
        )



        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        module = ABIModule.get_instance()
        api_key = module.configuration.sendgrid_api_key

        tools: list = []
        integration_config = SendGridIntegrationConfiguration(api_key=api_key)
        tools += as_tools(integration_config)

        intents: list = [
            Intent(
                intent_value="Get information about SendGrid email services",
                intent_type=IntentType.RAW,
                intent_target="SendGrid is an email delivery platform that provides transactional and marketing email services. I can provide general information, but I currently do not have access to SendGrid tools to perform operations."
            ),
            Intent(
                intent_value="Understand email delivery and management",
                intent_type=IntentType.RAW,
                intent_target="Email delivery involves sending emails through SMTP or API. I can explain best practices, but I currently do not have access to tools to send or manage emails."
            ),
        ]

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            agents=[],
            intents=intents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
