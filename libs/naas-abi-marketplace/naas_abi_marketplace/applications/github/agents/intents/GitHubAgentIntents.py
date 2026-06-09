from naas_abi_core.services.agent.IntentAgent import (
    Intent,
    IntentType,
)

INTENTS: list = [
    Intent(
        intent_value="Get details about a GitHub user",
        intent_type=IntentType.TOOL,
        intent_target="github_get_user_details",
    ),
    Intent(
        intent_value="Create a new repository for the user",
        intent_type=IntentType.TOOL,
        intent_target="github_create_user_repository",
    ),
    Intent(
        intent_value="Get details about a GitHub repository",
        intent_type=IntentType.TOOL,
        intent_target="github_get_repository_details",
    ),
    Intent(
        intent_value="List repositories for the specified organization in GitHub",
        intent_type=IntentType.TOOL,
        intent_target="github_list_organization_repositories",
    ),
    Intent(
        intent_value="Create a new repository for an organization",
        intent_type=IntentType.TOOL,
        intent_target="github_create_organization_repository",
    ),
    Intent(
        intent_value="Update a repository for an organization",
        intent_type=IntentType.TOOL,
        intent_target="github_update_organization_repository",
    ),
    Intent(
        intent_value="Delete a repository for an organization",
        intent_type=IntentType.TOOL,
        intent_target="github_delete_organization_repository",
    ),
    Intent(
        intent_value="Get a list of activities for the specified repository",
        intent_type=IntentType.TOOL,
        intent_target="github_list_repository_activities",
    ),
    Intent(
        intent_value="Get a list of contributors for the specified repository",
        intent_type=IntentType.TOOL,
        intent_target="github_get_repository_contributors",
    ),
    Intent(
        intent_value="Create an issue in the specified repository",
        intent_type=IntentType.TOOL,
        intent_target="github_create_issue",
    ),
    Intent(
        intent_value="Get an issue from a repository",
        intent_type=IntentType.TOOL,
        intent_target="github_get_issue",
    ),
    Intent(
        intent_value="Get issues from a repository",
        intent_type=IntentType.TOOL,
        intent_target="github_list_issues",
    ),
    Intent(
        intent_value="Get comments on an issue or pull request",
        intent_type=IntentType.TOOL,
        intent_target="github_list_issue_comments",
    ),
    Intent(
        intent_value="Get a comment on an issue or pull request",
        intent_type=IntentType.TOOL,
        intent_target="github_get_issue_comment",
    ),
    Intent(
        intent_value="Update a comment on an issue or pull request",
        intent_type=IntentType.TOOL,
        intent_target="github_update_issue_comment",
    ),
    Intent(
        intent_value="Delete a comment on an issue or pull request",
        intent_type=IntentType.TOOL,
        intent_target="github_delete_issue_comment",
    ),
    Intent(
        intent_value="Create a comment on an issue or pull request",
        intent_type=IntentType.TOOL,
        intent_target="github_create_issue_comment",
    ),
    Intent(
        intent_value="Create a pull request in the specified repository",
        intent_type=IntentType.TOOL,
        intent_target="github_create_pull_request",
    ),
    Intent(
        intent_value="Get a list of assignees for the specified repository",
        intent_type=IntentType.TOOL,
        intent_target="github_list_assignees",
    ),
    Intent(
        intent_value="Check if a user can be assigned to a specific issue",
        intent_type=IntentType.TOOL,
        intent_target="github_check_assignee_permission",
    ),
    Intent(
        intent_value="Add assignees to an issue",
        intent_type=IntentType.TOOL,
        intent_target="github_add_assignees_to_issue",
    ),
    Intent(
        intent_value="Remove assignees from an issue",
        intent_type=IntentType.TOOL,
        intent_target="github_remove_assignees_from_issue",
    ),
    Intent(
        intent_value="List all secrets available in a GitHub repository without revealing their encrypted values",
        intent_type=IntentType.TOOL,
        intent_target="github_list_repository_secrets",
    ),
    Intent(
        intent_value="Get a secret from a GitHub repository",
        intent_type=IntentType.TOOL,
        intent_target="github_get_repository_secret",
    ),
    Intent(
        intent_value="Create or update a secret in a GitHub repository",
        intent_type=IntentType.TOOL,
        intent_target="github_create_or_update_repository_secret",
    ),
    Intent(
        intent_value="Delete a secret from a GitHub repository",
        intent_type=IntentType.TOOL,
        intent_target="github_delete_repository_secret",
    ),
    Intent(
        intent_value="List contributors to a GitHub repository",
        intent_type=IntentType.TOOL,
        intent_target="github_list_repository_contributors",
    ),
]
