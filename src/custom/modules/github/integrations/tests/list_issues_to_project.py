from src.custom.modules.github.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.custom.modules.github.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret, config
from pprint import pprint
access_token = secret.get("GITHUB_ACCESS_TOKEN")

github_integration_config = GithubIntegrationConfiguration(access_token=access_token)
github_integration = GithubIntegration(github_integration_config)

github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(access_token=access_token)
github_graphql_integration = GithubGraphqlIntegration(github_graphql_integration_config)


issues = github_integration.list_issues(config.github_project_repository, state="open")
print(f"Issues: {len(issues)}")

for issue in issues:
    pull_request = issue.get("pull_request")
    if pull_request is not None:
        continue
    
    pprint(issue)
    break