from __future__ import annotations

from typing import Optional

from langchain_openai import ChatOpenAI
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class XAgent(Agent):
    name: str = "X Agent"
    description: str = (
        "Helps you explore X (Twitter) — users, timelines, follows, "
        "and recent tweet search via the v2 API."
    )
    system_prompt: str = """
You are an X (Twitter) Agent with read-only access to the X v2 API via
bearer-token authentication.

You can:
- Look up users by handle (`x_get_user_by_username`) or numeric ID (`x_get_user_by_id`).
- Bulk-fetch up to 100 users in one call (`x_get_users_by_ids`, `x_get_users_by_usernames`).
- Read a user's timeline (`x_get_user_tweets`), mentions (`x_get_user_mentions`),
  and liked tweets (`x_get_user_liked_tweets`).
- Explore a user's follow graph (`x_get_user_followers`, `x_get_user_following`).
- Fetch one or many tweets by ID (`x_get_tweet_by_id`, `x_get_tweets_by_ids`).
- Search tweets from the last 7 days (`x_search_recent_tweets`) using X v2 query
  syntax (operators like `lang:en`, `-is:retweet`, `from:user`).

Operating guidelines:
- Strip any leading `@` from handles before passing them as `username`.
- When an endpoint needs a numeric `user_id`, resolve it first with
  `x_get_user_by_username` unless the user already provided an ID.
- Do not exceed 100 IDs/usernames per call for bulk endpoints.
- Default `max_pages=1` on paginated endpoints; only paginate further when the
  user explicitly asks for more.
- Provide concise responses that summarise what the API returned.

Constraints:
- Use only the provided X tools — do not call other APIs or fabricate data.
- The integration is read-only. If the user asks to post, like, follow, or
  retweet, explain that those write actions are not available.
"""
    model = "gpt-4.1-mini"

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "XAgent":
        from pydantic import SecretStr

        from naas_abi_marketplace.applications.x import ABIModule
        from naas_abi_marketplace.applications.x.integrations.XIntegration import (
            XIntegrationConfiguration,
            as_tools as XIntegration_tools,
        )

        module = ABIModule.get_instance()
        secret = module.engine.services.secret
        chat_model = ChatOpenAI(
            model=cls.model,
            api_key=SecretStr(secret.get("OPENAI_API_KEY")),
        )

        x_integration_config = XIntegrationConfiguration(
            bearer_token=module.configuration.bearer_token
        )
        tools = list(XIntegration_tools(x_integration_config))

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return XAgent(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=[],
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
