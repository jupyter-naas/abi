def create_agent():
    from abi.services.agent.Agent import Agent, AgentConfiguration
    from src import secret
    from langchain_openai import ChatOpenAI
    from langchain_core.tools import tool
    import subprocess
    import pyperclip
    model = ChatOpenAI(
        model="gpt-4o", 
        temperature=0, 
        api_key=secret.get("OPENAI_API_KEY")
    )

    @tool
    def git_diff() -> str:
        """
        Get the git diff and the branch name
        """
        branch_name = subprocess.check_output(["git", "branch", "--show-current"]).decode("utf-8").strip()
        diff = subprocess.check_output(["git", "diff", "main"]).decode("utf-8")
        return f"Branch name: {branch_name}\n\n{diff}"

    @tool
    def store_pull_request_description(description: str) -> str:
        """ 
        Store the pull request description in a file `pull_request_description.md`
        """
        with open("pull_request_description.md", "w") as f:
            f.write(description)
        return "Pull request description stored in `pull_request_description.md`"

    @tool
    def store_pull_request_description_to_clipboard() -> str:
        """
        Store the pull request description in the clipboard.
        """
        with open("pull_request_description.md", "r") as f:
            description = f.read()
        pyperclip.copy(description)
        return "Pull request description stored in the clipboard"

    class PullRequestDescriptionAgent(Agent):
        pass

    return PullRequestDescriptionAgent(
        name="Pull Request Description Agent",
        description="A agent to generate a description for a pull request",
        chat_model=model,
        tools=[git_diff, store_pull_request_description, store_pull_request_description_to_clipboard],
        agents=[],
        configuration=AgentConfiguration(system_prompt="""
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
        """),
    )
    