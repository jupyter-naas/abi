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
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Accept": "application/vnd.github.v3+json"
        }

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

    def create_issue(self, repo_name: str, title: str, body: str, labels: Optional[List[str]] = [], assignees: Optional[List[str]] = []) -> Dict:
        """Create an issue in the specified repository."""
        data = {
            "title": title,
            "body": body,
            "labels": labels or [],
            "assignees": assignees or []
        }
        return self._make_request("POST", f"/repos/{repo_name}/issues", data)

    def get_issue(self, repo_name: str, issue_id: str) -> Dict:
        """Get an issue from a repository."""
        return self._make_request("GET", f"/repos/{repo_name}/issues/{issue_id}")

    def get_issues(
            self, 
            repo_name: str, 
            filter: Optional[str] = "all", 
            state: Optional[str] = "open", 
            sort: Optional[str] = "created", 
            direction: Optional[str] = "desc",
            limit: Optional[int] = -1,
            since: Optional[str] = None,
            labels: Optional[str] = None, 
        ) -> List[Dict]:
        """Get issues from a repository.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            filter (str, optional): Filter issues by: assigned, created, mentioned, subscribed, repos, all. 
                Defaults to "assigned"
            state (str, optional): Filter issues by state: open, closed, all. Defaults to "open"
            labels (str, optional): Comma-separated list of label names. Example: "bug,ui,@high"
            sort (str, optional): Sort issues by: created, updated, comments. Defaults to "created"
            direction (str, optional): Sort direction: asc, desc. Defaults to "desc"
            since (str, optional): Only show results updated after timestamp (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)
            limit (int, optional): Maximum number of issues to return. If -1, returns all issues.
            
        Returns:
            List[Dict]: List of issues matching the specified criteria
        """
        all_issues = []
        page = 1
        per_page = 100  # Max allowed by GitHub API
        
        while True:
            params = {
                "filter": filter,
                "state": state,
                "sort": sort,
                "direction": direction,
                "pulls": False,
                "per_page": per_page,
                "page": page
            }
            
            if labels:
                params["labels"] = labels
            if since:
                params["since"] = since
                
            query_string = "&".join(f"{k}={v}" for k,v in params.items())
            response = self._make_request("GET", f"/repos/{repo_name}/issues?{query_string}")
            
            if len(response) == 0:
                break
                
            all_issues.extend(response)
            
            # Break if we've reached the requested limit
            if limit != -1 and len(all_issues) >= limit:
                all_issues = all_issues[:limit]
                break
                
            page += 1
            
        return all_issues

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
            name="get_github_user_details",
            description="Get detailed information about a specific GitHub user",
            func=lambda username: integration.get_user_details(username),
            args_schema=GetUserDetailsSchema
        )
    ]