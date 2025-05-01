from src.custom.modules.github.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.custom.modules.github.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret, config
from pprint import pprint
import pydash as _

access_token = secret.get("GITHUB_ACCESS_TOKEN")

github_integration_config = GithubIntegrationConfiguration(access_token=access_token)
github_integration = GithubIntegration(github_integration_config)

github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(access_token=access_token)
github_graphql_integration = GithubGraphqlIntegration(github_graphql_integration_config)


issues = github_integration.list_issues(config.github_project_repository, state="open")
print(f"Issues: {len(issues)}")

project_node_id = "PVT_kwDOBESWNM4AKRt3"
status_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
status_option_id = "97363483"
i = 0

for issue in issues:
    pull_request = issue.get("pull_request")
    if pull_request is not None:
        continue

    i += 1
    node_id = issue.get("node_id")
    project_item = github_graphql_integration.get_item_id_from_node_id(node_id)
    item_id = None
    for x in project_item.get("data").get("node").get("projectItems").get("nodes"):
        if x.get("project", {}).get("id") == project_node_id:
            item_id = _.get(x, "id")
            break
    if item_id is None:
        # Add each issue to the project
        result = github_graphql_integration.add_issue_to_project(
            project_node_id=project_node_id,
            issue_node_id=issue['node_id'],
            status_field_id=status_field_id,
            status_option_id=status_option_id,
        )
        print(f"===> {i} - Issue assigned to project: {result}")
    else:
        print(f"===> {i} - Issue {issue['number']} already assigned to project {project_node_id}")