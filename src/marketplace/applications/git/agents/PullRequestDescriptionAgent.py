from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from typing import Optional
from pydantic import SecretStr

NAME = "Pull_Request_Description_Agent"
DESCRIPTION = "A agent to generate a description for a pull request"
SYSTEM_PROMPT = """
You are a Github Pull Request Description Agent. You have access to three tools:
- `git_diff`: Get the git diff
- `store_pull_request_description`: Store the pull request description in a file `pull_request_description.md`
- `store_pull_request_description_to_clipboard`: Store the pull request description in the clipboard.

You must call the `git_diff` tool first to get the git diff.
Then, you must call the `store_pull_request_description` tool to store the pull request description in a file `pull_request_description.md` that you will generate from the git diff.
And finally, you must call the `store_pull_request_description_to_clipboard` tool to store the pull request description in the clipboard.

The pull request description must always start with:

```markdown
This pull request resolves #<branch_name_number>
```

Where <branch_name_number> is the number at the beginning of the branch name.
"""

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[Agent]:
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    from src import secret
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(
        model="gpt-4o", 
        temperature=0, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )

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
        diff = subprocess.check_output(["git", "diff", "origin/main", "--", ".", ":!uv.lock"]).decode("utf-8")
        return f"Branch name: {branch_name}\n\n{diff}"

    def store_pull_request_description(description: str) -> str:
        """
        Store the pull request description in a file `pull_request_description.md`
        """
        import os
        import shutil
        from datetime import datetime

        file_path = os.path.join("storage", "datastore", "git", "pull_request_description.md")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(description)
        shutil.copy(file_path, os.path.join(os.path.dirname(file_path), datetime.now().isoformat() + "_" + os.path.basename(file_path)))
        return "Pull request description stored in `pull_request_description.md`"

    # def store_pull_request_description_to_clipboard() -> str:
    #     """
    #     Store the pull request description in the clipboard.
    #     """
    #     import os
    #     import pyperclip # type: ignore

    #     file_path = os.path.join("storage", "datastore", "git", "pull_request_description.md")
    #     with open(file_path, "r") as f:
    #         description = f.read()
    #     pyperclip.copy(description)
    #     return "Pull request description stored in the clipboard"
    
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class PullRequestDescriptionSchema(BaseModel):
        description: str = Field(..., description="The pull request description")
    
    class EmptySchema(BaseModel):
        pass

    tools: list = [
            StructuredTool(
                name="git_diff",
                description="Get the git diff and the branch name",
                func=lambda : git_diff(),
                args_schema=EmptySchema,
            ),
            StructuredTool(
                name="store_pull_request_description",
                description="Store the pull request description in a file `pull_request_description.md`",
                func=lambda description: store_pull_request_description(description),
                args_schema=PullRequestDescriptionSchema,
            ),
            # StructuredTool(
            #     name="store_pull_request_description_to_clipboard",
            #     description="Store the pull request description in the clipboard.",
            #     func=lambda: store_pull_request_description_to_clipboard(),
            #     args_schema=EmptySchema,
            # ),
        ]

    return PullRequestDescriptionAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        configuration=AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    )

class PullRequestDescriptionAgent(Agent):
    pass