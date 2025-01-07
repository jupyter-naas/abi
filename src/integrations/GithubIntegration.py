from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from dataclasses import dataclass
import requests
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

LOGO_URL = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"

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
    """Github API integration client.
    
    This integration provides methods to interact with Github's API endpoints.
    """

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

    def create_user_repository(self, name: str, private: bool = False, description: str = "") -> Dict:
        """Create a new repository."""
        data = {
            "name": name,
            "private": private,
            "description": description
        }
        return self._make_request("POST", "/user/repos", data)
    
    def get_repository_details(self, repo_name: str) -> Dict:
        """Get a repository by full name (format: 'owner/repo')."""
        return self._make_request("GET", f"/repos/{repo_name}")

    def list_organization_repositories(self, org: str) -> List[Dict]:
        """Get all repositories for a given owner.
        
        Args:
            owner (str): The GitHub username or organization name
            
        Returns:
            List[Dict]: List of repository details owned by the specified owner
        """
        return self._make_request("GET", f"/users/{org}/repos")
    
    def get_repository_contributors(self, repo_name: str) -> List[Dict]:
        """Get a list of contributors for the specified repository.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            
        Returns:
            List[Dict]: List of contributors with their contribution details
        """
        return self._make_request("GET", f"/repos/{repo_name}/contributors")

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

    def list_issues(
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
    
    def list_issue_comments(
        self,
        repo_name: str,
        sort: str = "created",
        direction: str = "asc",
        since: Optional[str] = None,
        per_page: int = 30,
        page: int = 1
    ) -> List[Dict]:
        """List comments on issues and pull requests for a repository.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            sort (str, optional): Property to sort results by: created, updated. Defaults to "created"
            direction (str, optional): Sort direction: asc, desc. Defaults to "asc"
            since (str, optional): Only show results updated after timestamp (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)
            per_page (int, optional): Number of results per page (max 100). Defaults to 30
            page (int, optional): Page number of results to fetch. Defaults to 1
            
        Returns:
            List[Dict]: List of issue comments matching the specified criteria
        """
        params = {
            "sort": sort,
            "direction": direction,
            "per_page": min(per_page, 100),
            "page": page
        }
        
        if since:
            params["since"] = since
            
        query_string = "&".join(f"{k}={v}" for k,v in params.items())
        return self._make_request("GET", f"/repos/{repo_name}/issues/comments?{query_string}")
    
    def get_issue_comment(
        self,
        repo_name: str,
        comment_id: int,
        accept: str = "application/vnd.github+json"
    ) -> Dict:
        """Get a comment on an issue or pull request.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            comment_id (int): The unique identifier of the comment
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                Supported values:
                - application/vnd.github.raw+json: Returns raw markdown body
                - application/vnd.github.text+json: Returns text-only representation
                - application/vnd.github.html+json: Returns HTML rendered markdown
                - application/vnd.github.full+json: Returns raw, text and HTML representations
                
        Returns:
            Dict: The issue comment data
        """
        headers = {"Accept": accept}
        return self._make_request("GET", f"/repos/{repo_name}/issues/comments/{comment_id}", headers=headers)
    
    def update_issue_comment(
        self,
        repo_name: str,
        comment_id: int,
        body: str,
        accept: str = "application/vnd.github+json"
    ) -> Dict:
        """Update a comment on an issue or pull request.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            comment_id (int): The unique identifier of the comment
            body (str): The new contents of the comment
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                Supported values:
                - application/vnd.github.raw+json: Returns raw markdown body
                - application/vnd.github.text+json: Returns text-only representation
                - application/vnd.github.html+json: Returns HTML rendered markdown
                - application/vnd.github.full+json: Returns raw, text and HTML representations
                
        Returns:
            Dict: The updated issue comment data
        """
        headers = {"Accept": accept}
        data = {"body": body}
        return self._make_request("PATCH", f"/repos/{repo_name}/issues/comments/{comment_id}", headers=headers, data=data)
    
    def delete_issue_comment(
        self,
        repo_name: str,
        comment_id: int,
        accept: str = "application/vnd.github+json"
    ) -> None:
        """Delete a comment on an issue or pull request.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            comment_id (int): The unique identifier of the comment
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                
        Returns:
            None
        """
        headers = {"Accept": accept}
        self._make_request("DELETE", f"/repos/{repo_name}/issues/comments/{comment_id}", headers=headers)

    def create_issue_comment(
        self,
        repo_name: str,
        issue_number: int,
        body: str,
        accept: str = "application/vnd.github+json"
    ) -> Dict:
        """Create a comment on an issue or pull request.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            issue_number (int): The number that identifies the issue
            body (str): The contents of the comment
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                Supported values:
                - application/vnd.github.raw+json: Returns raw markdown body
                - application/vnd.github.text+json: Returns text-only representation
                - application/vnd.github.html+json: Returns HTML rendered markdown
                - application/vnd.github.full+json: Returns raw, text and HTML representations
                
        Returns:
            Dict: The created issue comment data
        """
        headers = {"Accept": accept}
        data = {"body": body}
        return self._make_request("POST", f"/repos/{repo_name}/issues/{issue_number}/comments", headers=headers, data=data)

    def create_pull_request(self, repo_name: str, title: str, body: str, head: str, base: str) -> Dict:
        """Create a pull request."""
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        return self._make_request("POST", f"/repos/{repo_name}/pulls", data)
    
    def list_assignees(
        self,
        repo_name: str,
        per_page: int = 30,
        page: int = 1,
        accept: str = "application/vnd.github+json"
    ) -> Dict:
        """Lists the available assignees for issues in a repository.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            per_page (int, optional): Number of results per page (max 100). Defaults to 30
            page (int, optional): Page number of results to fetch. Defaults to 1
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                
        Returns:
            Dict: List of available assignees for the repository
        """
        headers = {"Accept": accept}
        params = {
            "per_page": per_page,
            "page": page
        }
        return self._make_request("GET", f"/repos/{repo_name}/assignees", headers=headers, params=params)
    
    def check_assignee(
        self,
        repo_name: str,
        assignee: str,
        accept: str = "application/vnd.github+json"
    ) -> bool:
        """Check if a user can be assigned to issues in a repository.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            assignee (str): Username to check assignability for
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                
        Returns:
            bool: True if user can be assigned, False otherwise
        """
        headers = {"Accept": accept}
        try:
            self._make_request("GET", f"/repos/{repo_name}/assignees/{assignee}", headers=headers)
            return True
        except IntegrationConnectionError:
            return False
        
    def add_assignees_to_issue(
        self,
        repo_name: str,
        issue_number: int,
        assignees: List[str],
        accept: str = "application/vnd.github+json"
    ) -> Dict:
        """Adds up to 10 assignees to an issue. Users already assigned to an issue are not replaced.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            issue_number (int): The number that identifies the issue
            assignees (List[str]): Usernames of people to assign this issue to
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                
        Returns:
            Dict: Updated issue information
            
        Note:
            Only users with push access can add assignees to an issue. 
            Assignees are silently ignored otherwise.
        """
        headers = {"Accept": accept}
        data = {"assignees": assignees}
        return self._make_request(
            "POST", 
            f"/repos/{repo_name}/issues/{issue_number}/assignees",
            headers=headers,
            data=data
        )
    
    def remove_assignees_from_issue(
        self,
        repo_name: str,
        issue_number: int,
        assignees: List[str],
        accept: str = "application/vnd.github+json"
    ) -> Dict:
        """Removes one or more assignees from an issue.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            issue_number (int): The number that identifies the issue
            assignees (List[str]): Usernames of assignees to remove from the issue
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                
        Returns:
            Dict: Updated issue information
            
        Note:
            Only users with push access can remove assignees from an issue.
            Assignees are silently ignored otherwise.
        """
        headers = {"Accept": accept}
        data = {"assignees": assignees}
        return self._make_request(
            "DELETE",
            f"/repos/{repo_name}/issues/{issue_number}/assignees",
            headers=headers,
            data=data
        )
    
    def check_assignee_permission(
        self,
        repo_name: str,
        issue_number: int,
        assignee: str,
        accept: str = "application/vnd.github+json"
    ) -> bool:
        """Checks if a user can be assigned to a specific issue.
        
        Args:
            repo_name (str): Repository name in 'owner/repo' format
            issue_number (int): The number that identifies the issue
            assignee (str): Username of the assignee to check
            accept (str, optional): Media type for the response format. Defaults to "application/vnd.github+json"
                
        Returns:
            bool: True if user can be assigned, False otherwise
            
        Note:
            Returns True (204 status code) if assignee can be assigned.
            Returns False (404 status code) if assignee cannot be assigned.
            Can be used without authentication for public repositories.
        """
        headers = {"Accept": accept}
        try:
            self._make_request(
                "GET",
                f"/repos/{repo_name}/issues/{issue_number}/assignees/{assignee}",
                headers=headers
            )
            return True
        except IntegrationConnectionError:
            return False
    
def as_tools(configuration: GithubIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration : GithubIntegration = GithubIntegration(configuration)

    class GetUserDetailsSchema(BaseModel):
        username: str = Field(..., description="GitHub username of the user to fetch details for")

    class CreateUserRepositorySchema(BaseModel):
        name: str = Field(..., description="Name of the repository to create")
        private: bool = Field(..., description="Whether the repository should be private")
        description: str = Field(..., description="Description of the repository")

    class GetRepositorySchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")

    class ListOrganizationRepositoriesSchema(BaseModel):
        org: str = Field(..., description="GitHub organization name")

    class GetRepositoryContributorsSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")

    class CreateIssueSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        title: str = Field(..., description="Title of the issue")
        body: str = Field(..., description="Body of the issue")
        labels: List[str] = Field(..., description="Labels to apply to the issue")
        assignees: List[str] = Field(..., description="Assignees to assign to the issue")

    class GetIssueSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        issue_id: str = Field(..., description="ID of the issue to fetch")

    class GetIssuesSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        filter: str = Field(..., description="Filter issues by: assigned, created, mentioned, subscribed, repos, all")
        state: str = Field(..., description="Filter issues by state: open, closed, all")
        sort: str = Field(..., description="Sort issues by: created, updated, comments")
        direction: str = Field(..., description="Sort direction: asc, desc")
        limit: int = Field(..., description="Maximum number of issues to return")
        since: str = Field(..., description="Only show results updated after timestamp (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)")
        labels: str = Field(..., description="Comma-separated list of label names. Example: 'bug,ui,@high'")

    class ListIssueCommentsSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        sort: str = Field(..., description="Property to sort results by: created, updated")
        direction: str = Field(..., description="Sort direction: asc, desc")
        since: str = Field(..., description="Only show results updated after timestamp (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)")
        per_page: int = Field(..., description="Number of results per page (max 100)")
        page: int = Field(..., description="Page number of results to fetch")

    class GetIssueCommentSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        comment_id: int = Field(..., description="ID of the comment to fetch")

    class UpdateIssueCommentSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        comment_id: int = Field(..., description="ID of the comment to update")
        body: str = Field(..., description="New body of the comment")

    class DeleteIssueCommentSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        comment_id: int = Field(..., description="ID of the comment to delete")

    class CreateIssueCommentSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        issue_number: int = Field(..., description="ID of the issue to comment on")
        body: str = Field(..., description="Body of the comment")

    class CreatePullRequestSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        title: str = Field(..., description="Title of the pull request")
        body: str = Field(..., description="Body of the pull request")
        head: str = Field(..., description="Branch to merge into base")
        base: str = Field(..., description="Base branch to merge from")

    class ListAssigneesSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")

    class CheckAssigneePermissionSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        issue_number: int = Field(..., description="ID of the issue to check assignee permission for")
        assignee: str = Field(..., description="Username of the assignee to check")

    class AddAssigneesToIssueSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        issue_number: int = Field(..., description="ID of the issue to add assignees to")
        assignees: List[str] = Field(..., description="Usernames of people to assign this issue to")

    class RemoveAssigneesFromIssueSchema(BaseModel):
        repo_name: str = Field(..., description="Full repository name in format 'owner/repo'")
        issue_number: int = Field(..., description="ID of the issue to remove assignees from")
        assignees: List[str] = Field(..., description="Usernames of assignees to remove from the issue")
    
    return [
        StructuredTool(
            name="get_user_details",
            description="Get details about a GitHub user",
            func=lambda username: integration.get_user_details(username),
            args_schema=GetUserDetailsSchema
        ),
        StructuredTool(
            name="create_user_repository",
            description="Create a new repository for the user",
            func=lambda name, private, description: integration.create_user_repository(name, private, description),
            args_schema=CreateUserRepositorySchema
        ),
        StructuredTool(
            name="get_repository_details",
            description="Get details about a GitHub repository",
            func=lambda repo_name: integration.get_repository_details(repo_name),
            args_schema=GetRepositorySchema
        ),
        StructuredTool(
            name="list_organization_repositories",
            description="Lists repositories for the specified organization in GitHub",
            func=lambda org: integration.list_organization_repositories(org),
            args_schema=ListOrganizationRepositoriesSchema
        ),
        StructuredTool(
            name="get_repository_contributors",
            description="Get a list of contributors for the specified repository",
            func=lambda repo_name: integration.get_repository_contributors(repo_name),
            args_schema=GetRepositoryContributorsSchema
        ),
        StructuredTool(
            name="create_issue",
            description="Create an issue in the specified repository",
            func=lambda repo_name, title, body, labels, assignees: integration.create_issue(repo_name, title, body, labels, assignees),
            args_schema=CreateIssueSchema
        ),
        StructuredTool(
            name="get_issue",
            description="Get an issue from a repository",
            func=lambda repo_name, issue_id: integration.get_issue(repo_name, issue_id),
            args_schema=GetIssueSchema
        ),
        StructuredTool(
            name="list_issues",
            description="Get issues from a repository",
            func=lambda repo_name, filter, state, sort, direction, limit, since, labels: integration.list_issues(repo_name, filter, state, sort, direction, limit, since, labels),
            args_schema=GetIssuesSchema
        ),
        StructuredTool(
            name="list_issue_comments",
            description="Get comments on an issue or pull request",
            func=lambda repo_name, sort, direction, since, per_page, page: integration.list_issue_comments(repo_name, sort, direction, since, per_page, page),
            args_schema=ListIssueCommentsSchema
        ),
        StructuredTool(
            name="get_issue_comment",
            description="Get a comment on an issue or pull request",
            func=lambda repo_name, comment_id: integration.get_issue_comment(repo_name, comment_id),
            args_schema=GetIssueCommentSchema
        ),
        StructuredTool(
            name="update_issue_comment",
            description="Update a comment on an issue or pull request",
            func=lambda repo_name, comment_id, body: integration.update_issue_comment(repo_name, comment_id, body),
            args_schema=UpdateIssueCommentSchema
        ),
        StructuredTool(
            name="delete_issue_comment",
            description="Delete a comment on an issue or pull request",
            func=lambda repo_name, comment_id: integration.delete_issue_comment(repo_name, comment_id),
            args_schema=DeleteIssueCommentSchema
        ),
        StructuredTool(
            name="create_issue_comment",
            description="Create a comment on an issue or pull request",
            func=lambda repo_name, issue_number, body: integration.create_issue_comment(repo_name, issue_number, body),
            args_schema=CreateIssueCommentSchema
        ),
        StructuredTool(
            name="create_pull_request",
            description="Create a pull request in the specified repository",
            func=lambda repo_name, title, body, head, base: integration.create_pull_request(repo_name, title, body, head, base),
            args_schema=CreatePullRequestSchema
        ),
        StructuredTool(
            name="list_assignees",
            description="Get a list of assignees for the specified repository",
            func=lambda repo_name: integration.list_assignees(repo_name),
            args_schema=ListAssigneesSchema
        ),
        StructuredTool(
            name="check_assignee_permission",
            description="Check if a user can be assigned to a specific issue",
            func=lambda repo_name, issue_number, assignee: integration.check_assignee_permission(repo_name, issue_number, assignee),
            args_schema=CheckAssigneePermissionSchema
        ),
        StructuredTool(
            name="add_assignees_to_issue",
            description="Add assignees to an issue",
            func=lambda repo_name, issue_number, assignees: integration.add_assignees_to_issue(repo_name, issue_number, assignees),
            args_schema=AddAssigneesToIssueSchema
        ),
        StructuredTool(
            name="remove_assignees_from_issue",
            description="Remove assignees from an issue",
            func=lambda repo_name, issue_number, assignees: integration.remove_assignees_from_issue(repo_name, issue_number, assignees),
            args_schema=RemoveAssigneesFromIssueSchema
        )
    ]
