import requests
from typing import Dict, List, Optional

from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from dataclasses import dataclass
from pydantic import BaseModel, Field

@dataclass
class GithubIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Github integration.
    
    Attributes:
        access_token (str): Github personal access token for authentication
        base_url (str): Base URL for Github API, defaults to https://api.github.com
    """
    access_token: str
    base_url: str = "https://api.github.com"

class GithubIntegration(Integration):

    __configuration: GithubIntegrationConfiguration

    def __init__(self, configuration: GithubIntegrationConfiguration):
        """Initialize Github client with access token."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # # Test connection
        # try:
        #     self._make_request("GET", "/user")
        # except Exception as e:
        #     raise IntegrationConnectionError(f"Failed to connect to Github: {str(e)}")

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to Github API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Github API request failed: {str(e)}")

    def list_organization_repositories(self, org: str) -> List[Dict]:
        """Get all repositories for a given owner.
        
        Args:
            owner (str): The GitHub username or organization name
            
        Returns:
            List[Dict]: List of repository details owned by the specified owner
        """
        return self._make_request("GET", f"/users/{org}/repos")

    def get_repository(self, repo_name: str) -> Dict:
        """Get a repository by full name (format: 'owner/repo')."""
        return self._make_request("GET", f"/repos/{repo_name}")

    def create_issue(self, repo_name: str, title: str, body: str, labels: Optional[List[str]] = None) -> Dict:
        """Create an issue in the specified repository."""
        data = {
            "title": title,
            "body": body,
            "labels": labels or []
        }
        return self._make_request("POST", f"/repos/{repo_name}/issues", data)

    def get_issue(self, repo_name: str, issue_id: str) -> Dict:
        """Get an issue from a repository."""
        return self._make_request("GET", f"/repos/{repo_name}/issues/{issue_id}")

    def get_issues(self, repo_name: str, state: str = "open") -> List[Dict]:
        """Get issues from a repository."""
        return self._make_request("GET", f"/repos/{repo_name}/issues?state={state}")

    def create_pull_request(self, repo_name: str, title: str, body: str, head: str, base: str) -> Dict:
        """Create a pull request."""
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        return self._make_request("POST", f"/repos/{repo_name}/pulls", data)

    def get_user(self) -> Dict:
        """Get authenticated user information."""
        return self._make_request("GET", "/user")

    def create_repository(self, name: str, private: bool = False, description: str = "") -> Dict:
        """Create a new repository."""
        data = {
            "name": name,
            "private": private,
            "description": description
        }
        return self._make_request("POST", "/user/repos", data)

    def get_repository_contributors(self, repo_name: str) -> List[Dict]:
        """Get a list of contributors for the specified repository.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            
        Returns:
            List[Dict]: List of contributors with their contribution details
        """
        return self._make_request("GET", f"/repos/{repo_name}/contributors")

    def get_user_details(self, username: str) -> Dict:
        """Get detailed information about a specific GitHub user.
        
        Args:
            username (str): The GitHub username of the user
            
        Returns:
            Dict: Detailed user information including:
                - Name
                - Bio
                - Location
                - Email
                - Number of public repos
                - Number of followers
                - Company
                - Blog URL
                - And more
        """
        return self._make_request("GET", f"/users/{username}")
    
def as_tools(configuration: GithubIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration : GithubIntegration = GithubIntegration(configuration)

    class ListOrganizationRepositoriesSchema(BaseModel):
        org: str = Field(..., description="GitHub organization name")

    class GetRepositorySchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")

    class CreateIssueSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        title: str = Field(..., description="Title of the issue (mandatory)")
        body: str = Field(..., description="Content/description of the issue (mandatory)")
        labels: Optional[List[str]] = Field(None, description="List of labels to apply to the issue (optional)")

    # class GetIssuesSchema(BaseModel):
    #     repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
    #     state: str = Field("open", description="State of issues to fetch: 'open', 'closed', or 'all'")

    class CreatePullRequestSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        title: str = Field(..., description="Title of the pull request")
        body: str = Field(..., description="Description of the pull request")
        head: str = Field(..., description="Name of the branch where changes are implemented")
        base: str = Field(..., description="Name of the branch where changes should be pulled into")

    class CreateRepositorySchema(BaseModel):
        name: str = Field(..., description="Name of the new repository")
        private: bool = Field(False, description="Whether the repository should be private")
        description: str = Field("", description="Description of the repository")

    class GetContributorsSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")

    class GetUserDetailsSchema(BaseModel):
        username: str = Field(..., description="GitHub username of the user to fetch details for")
    
    return [
        StructuredTool(
            name="list_github_organization_repositories",
            description="Lists repositories for the specified organization in GitHub",
            func=lambda org: integration.list_organization_repositories(org),
            args_schema=ListOrganizationRepositoriesSchema
        ),
        StructuredTool(
            name="get_github_repository",
            description="Get details about a GitHub repository",
            func=lambda repo_name: integration.get_repository(repo_name),
            args_schema=GetRepositorySchema
        ),
        StructuredTool(
            name="create_github_issue",
            description="Create a new issue in a GitHub repository.",
            func=lambda repo_name, title, body, labels=None: integration.create_issue(repo_name, title, body, labels),
            args_schema=CreateIssueSchema
        ),
        # StructuredTool(
        #     name="get_github_issues",
        #     description="Get list of issues from a GitHub repository",
        #     func=lambda repo_name, state="open": integration.get_issues(repo_name, state),
        #     args_schema=GetIssuesSchema
        # ),
        StructuredTool(
            name="create_github_pull_request",
            description="Create a new pull request in a GitHub repository",
            func=lambda repo_name, title, body, head, base: integration.create_pull_request(repo_name, title, body, head, base),
            args_schema=CreatePullRequestSchema
        ),
        StructuredTool(
            name="get_github_user",
            description="Get information about the authenticated GitHub user",
            func=lambda: integration.get_user(),
            args_schema=None
        ),
        StructuredTool(
            name="create_github_repository",
            description="Create a new GitHub repository",
            func=lambda name, private=False, description="": integration.create_repository(name, private, description),
            args_schema=CreateRepositorySchema
        ),
        StructuredTool(
            name="get_github_repository_contributors",
            description="Get list of contributors for a GitHub repository",
            func=lambda repo_name: integration.get_repository_contributors(repo_name),
            args_schema=GetContributorsSchema
        ),
        StructuredTool(
            name="get_github_user_details",
            description="Get detailed information about a specific GitHub user",
            func=lambda username: integration.get_user_details(username),
            args_schema=GetUserDetailsSchema
        )
    ]