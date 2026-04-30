from typing import Optional

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class PullRequestDescriptionAgent(Agent):
    name: str = "Pull Request Description Agent"
    description: str = "A agent to generate a description for a pull request"
    system_prompt: str = """
You are a Github Pull Request Description Agent. You have access to three tools:
- `git_diff`: Get the git diff
- `store_pull_request_description`: Store the pull request description in a file `pull_request_description.md`

You must call the `git_diff` tool first to get the git diff.
Then, you must call the `store_pull_request_description` tool to store the pull request description in a file `pull_request_description.md` that you will generate from the git diff.
Finally, display the pull request description must always start with:

```markdown
This pull request resolves #<branch_name_number>
```

Where <branch_name_number> is the number at the beginning of the branch name.
"""
    model = "gpt-4.1-mini"

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "PullRequestDescriptionAgent":
        from naas_abi_marketplace.applications.git import ABIModule
        from pydantic import SecretStr

        module = ABIModule.get_instance()
        secret = module.engine.services.secret
        object_storage = module.engine.services.object_storage
        model = ChatOpenAI(
            model=cls.model, api_key=SecretStr(secret.get("OPENAI_API_KEY"))
        )

        @tool(description="Get the git diff and the branch name")
        def git_diff() -> str:
            """
            Get the git diff and the branch name
            """
            import subprocess

            branch_name = (
                subprocess.check_output(["git", "branch", "--show-current"])
                .decode("utf-8")
                .strip()
            )
            diff = subprocess.check_output(
                ["git", "diff", "origin/main", "--", ".", ":!uv.lock"]
            ).decode("utf-8")
            return f"Branch name: {branch_name}\n\n{diff}"

        @tool(
            description="Store the pull request description in a file `pull_request_description.md`"
        )
        def store_pull_request_description(description: str) -> str:
            """
            Store the pull request description in a file `pull_request_description.md`
            """
            if object_storage is None:
                return "Object storage is not available (module not initialized)."

            object_storage.put_object(
                prefix="git",
                key="pull_request_description.md",
                content=description.encode("utf-8"),
            )
            return (
                "Pull request description stored in `git/pull_request_description.md`"
            )

        # Set configuration
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt,
            )
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return PullRequestDescriptionAgent(
            name=cls.name,
            description=cls.description,
            chat_model=model,
            tools=[git_diff, store_pull_request_description],
            agents=[],
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
