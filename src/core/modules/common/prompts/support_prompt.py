SUPPORT_CHAIN_OF_THOUGHT_PROMPT = """
Chain of thought for support_agent:
1.1. Identify if the user intent:
  - Feature request: New integration with external API, new ontology pipeline, or new workflow
  - Bug report: Issue with existing integration, pipeline, or workflow

1.2. Use `support_agent_list_issues` tool to check for similar issues. Get more details about the issue using `support_agent_get_details` tool.

1.3.1. If no similar issue, you MUST generate the draft proposition with a title and description based on the user request.
1.3.2. If similar issue, display its details and propose following options to the user:
    - Create new issue (include draft in your response)
    - Update existing issue (include proposed updates in your response)
    - Take no action

1.4. After explicit user approval use appropriate tool to complete your task: "support_agent_create_bug_report" or "support_agent_create_feature_request".
"""