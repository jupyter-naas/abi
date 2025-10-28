from abi.integration.integration import (
    Integration,
    IntegrationConnectionError,
    IntegrationConfiguration,
)
from dataclasses import dataclass
import requests
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


@dataclass
class GitHubIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Github integration.

    Attributes:
        access_token (str): Github personal access token for authentication
        base_url (str): Base URL for Github API, defaults to https://api.github.com
    """

    access_token: str
    base_url: str = "https://api.github.com"


class GitHubIntegration(Integration):
    """Github API integration client.

    This integration provides methods to interact with Github's API endpoints.
    """

    __configuration: GitHubIntegrationConfiguration

    def __init__(self, configuration: GitHubIntegrationConfiguration):
        """Initialize Github client with access token."""
        self.__configuration = configuration

        self.headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None, 
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict | List:
        """Make HTTP request to Github API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)
        try:
            response = requests.request(
                method=method, 
                url=url, 
                headers=request_headers, 
                json=data, 
                params=params
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

    def create_user_repository(
        self, name: str, private: bool = False, description: str = ""
    ) -> Dict:
        """Create a new repository."""
        data = {"name": name, "private": private, "description": description}
        return self._make_request("POST", "/user/repos", data)

    def get_repository_details(self, repo_name: str) -> Dict:
        """Get a repository by full name (format: 'owner/repo')."""
        return self._make_request("GET", f"/repos/{repo_name}")

    def list_organization_repositories(self, org: str, return_list: bool = False) -> list:
        """Get all repositories for a given owner.

        Args:
            owner (str): The GitHub username or organization name

        Returns:
            List[Dict]: List of repository details owned by the specified owner
        """
        params = {"page": 1, "per_page": 100, "sort": "full_name"}
        response = self._make_request("GET", f"/orgs/{org}/repos", params=params)
        if return_list:
            return [{repo["name"], repo["full_name"]} for repo in response]
        return response

    def create_organization_repository(
        self, org: str, name: str, private: bool = True, description: str = ""
    ) -> Dict:
        """Create a new repository for an organization."""
        data = {"name": name, "private": private, "description": description}
        return self._make_request("POST", f"/orgs/{org}/repos", data)

    def update_organization_repository(
        self,
        org: str,
        repo_name: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        homepage: Optional[str] = None,
        private: Optional[bool] = None,
        visibility: Optional[str] = None,
        security_and_analysis: Optional[Dict] = None,
        has_issues: Optional[bool] = None,
        has_projects: Optional[bool] = None,
        has_wiki: Optional[bool] = None,
        is_template: Optional[bool] = None,
        default_branch: Optional[str] = None,
        allow_squash_merge: Optional[bool] = None,
        allow_merge_commit: Optional[bool] = None,
        allow_rebase_merge: Optional[bool] = None,
        allow_auto_merge: Optional[bool] = None,
        delete_branch_on_merge: Optional[bool] = None,
        allow_update_branch: Optional[bool] = None,
        use_squash_pr_title_as_default: Optional[bool] = None,
        squash_merge_commit_title: Optional[str] = None,
        squash_merge_commit_message: Optional[str] = None,
        merge_commit_title: Optional[str] = None,
        merge_commit_message: Optional[str] = None,
        archived: Optional[bool] = None,
        allow_forking: Optional[bool] = None,
        web_commit_signoff_required: Optional[bool] = None,
        accept: str = "application/vnd.github+json",
    ) -> Dict:
        """Updates a repository for an organization.

        Args:
            org (str): The organization name (case insensitive)
            repo_name (str): The repository name without .git extension (case insensitive)
            name (str, optional): New name of the repository
            description (str, optional): Short description of the repository
            homepage (str, optional): URL with more information about the repository
            private (bool, optional): Make repository private (true) or public (false)
            visibility (str, optional): Repository visibility: "public" or "private"
            security_and_analysis (Dict, optional): Security and analysis feature settings
            has_issues (bool, optional): Enable/disable issues
            has_projects (bool, optional): Enable/disable projects
            has_wiki (bool, optional): Enable/disable wiki
            is_template (bool, optional): Make repository available as template
            default_branch (str, optional): Update default branch
            allow_squash_merge (bool, optional): Enable/disable squash-merging
            allow_merge_commit (bool, optional): Enable/disable merge commits
            allow_rebase_merge (bool, optional): Enable/disable rebase-merging
            allow_auto_merge (bool, optional): Enable/disable auto-merge
            delete_branch_on_merge (bool, optional): Enable/disable auto branch deletion
            allow_update_branch (bool, optional): Enable/disable updating branches behind base
            use_squash_pr_title_as_default (bool, optional): Use PR title for squash merges
            squash_merge_commit_title (str, optional): Default squash merge commit title
            squash_merge_commit_message (str, optional): Default squash merge commit message
            merge_commit_title (str, optional): Default merge commit title
            merge_commit_message (str, optional): Default merge commit message
            archived (bool, optional): Archive/unarchive repository
            allow_forking (bool, optional): Enable/disable private forks
            web_commit_signoff_required (bool, optional): Require signoff on web commits
            accept (str, optional): Media type. Defaults to "application/vnd.github+json"

        Returns:
            Dict: Updated repository information

        Note:
            - Requires admin permissions or owner/security manager role
            - For security_and_analysis changes, admin/owner/security manager required
            - Some org settings may restrict changing repository visibility
        """
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if homepage is not None:
            data["homepage"] = homepage
        if private is not None:
            data["private"] = private
        if visibility is not None:
            data["visibility"] = visibility
        if security_and_analysis is not None:
            data["security_and_analysis"] = security_and_analysis
        if has_issues is not None:
            data["has_issues"] = has_issues
        if has_projects is not None:
            data["has_projects"] = has_projects
        if has_wiki is not None:
            data["has_wiki"] = has_wiki
        if is_template is not None:
            data["is_template"] = is_template
        if default_branch is not None:
            data["default_branch"] = default_branch
        if allow_squash_merge is not None:
            data["allow_squash_merge"] = allow_squash_merge
        if allow_merge_commit is not None:
            data["allow_merge_commit"] = allow_merge_commit
        if allow_rebase_merge is not None:
            data["allow_rebase_merge"] = allow_rebase_merge
        if allow_auto_merge is not None:
            data["allow_auto_merge"] = allow_auto_merge
        if delete_branch_on_merge is not None:
            data["delete_branch_on_merge"] = delete_branch_on_merge
        if allow_update_branch is not None:
            data["allow_update_branch"] = allow_update_branch
        if use_squash_pr_title_as_default is not None:
            data["use_squash_pr_title_as_default"] = use_squash_pr_title_as_default
        if squash_merge_commit_title is not None:
            data["squash_merge_commit_title"] = squash_merge_commit_title
        if squash_merge_commit_message is not None:
            data["squash_merge_commit_message"] = squash_merge_commit_message
        if merge_commit_title is not None:
            data["merge_commit_title"] = merge_commit_title
        if merge_commit_message is not None:
            data["merge_commit_message"] = merge_commit_message
        if archived is not None:
            data["archived"] = archived
        if allow_forking is not None:
            data["allow_forking"] = allow_forking
        if web_commit_signoff_required is not None:
            data["web_commit_signoff_required"] = web_commit_signoff_required

        return self._make_request(
            "PATCH", 
            f"/repos/{org}/{repo_name}", 
            headers={"Accept": accept}, 
            data=data
        )

    def delete_repository(
        self, 
        repo_name: str, 
        accept: str = "application/vnd.github+json"
    ) -> None:
        """Deletes a repository."""
        self._make_request(
            "DELETE", 
            f"/repos/{repo_name}", 
            headers={"Accept": accept}
        )

    def list_repository_activities(
        self,
        repo_name: str,
        direction: str = "desc",
        per_page: int = 30,
        before: Optional[str] = None,
        after: Optional[str] = None,
        ref: Optional[str] = None,
        actor: Optional[str] = None,
        time_period: Optional[str] = None,
        activity_type: Optional[str] = None,
        accept: str = "application/vnd.github+json",
    ) -> Dict:
        """Lists a detailed history of changes to a repository.

        Args:
            repo_name (str): Repository name in 'owner/repo' format
            direction (str, optional): Sort direction: asc, desc. Defaults to "desc"
            per_page (int, optional): Number of results per page (max 100). Defaults to 30
            before (str, optional): Cursor for pagination - only returns results before this cursor
            after (str, optional): Cursor for pagination - only returns results after this cursor
            ref (str, optional): Git reference to filter activities by (e.g. branch name)
            actor (str, optional): GitHub username to filter by actor who performed activity
            time_period (str, optional): Time period to filter by: day, week, month, quarter, year
            activity_type (str, optional): Activity type to filter by: push, force_push,
                branch_creation, branch_deletion, pr_merge, merge_queue_merge
            accept (str, optional): Media type for response format. Defaults to "application/vnd.github+json"

        Returns:
            Dict: Repository activity data

        Note:
            - Works without authentication for public repositories
            - OAuth tokens need repo scope
            - Fine-grained tokens need "Contents" repository read permissions
        """
        headers = {"Accept": accept}
        params = {"direction": direction, "per_page": per_page}

        if before:
            params["before"] = before
        if after:
            params["after"] = after
        if ref:
            params["ref"] = ref
        if actor:
            params["actor"] = actor
        if time_period:
            params["time_period"] = time_period
        if activity_type:
            params["activity_type"] = activity_type

        return self._make_request(
            "GET", f"/repos/{repo_name}/activity", headers=headers, params=params
        )

    def get_repository_contributors(self, repo_name: str) -> Dict:
        """Get a list of contributors for the specified repository.

        Args:
            repo_name (str): Repository name in 'owner/repo' format

        Returns:
            List[Dict]: List of contributors with their contribution details
        """
        return self._make_request("GET", f"/repos/{repo_name}/contributors")

    def create_issue(
        self,
        repo_name: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = [],
        assignees: Optional[List[str]] = [],
    ) -> Dict:
        """Create an issue in the specified repository."""
        data = {
            "title": title,
            "body": body,
            "labels": labels or [],
            "assignees": assignees or [],
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
        all_issues: List[Dict] = []
        page = 1
        per_page = 100  # Max allowed by GitHub API

        while True:
            params = {
                "filter": filter,
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": per_page,
                "page": page,
            }

            if labels:
                params["labels"] = labels
            if since:
                params["since"] = since

            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            response = self._make_request(
                "GET", f"/repos/{repo_name}/issues?{query_string}"
            )

            if not isinstance(response, list):
                break

            all_issues.extend(response)

            # Break if we've reached the requested limit
            if limit is not None and limit != -1 and len(all_issues) >= limit:
                all_issues = all_issues[:limit]
                break

            if len(response) == 0:
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
        page: int = 1,
    ) -> Dict:
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
            "page": page,
        }

        if since:
            params["since"] = since

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return self._make_request(
            "GET", f"/repos/{repo_name}/issues/comments?{query_string}"
        )

    def get_issue_comment(
        self,
        repo_name: str,
        comment_id: int,
        accept: str = "application/vnd.github+json",
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
        return self._make_request(
            "GET", f"/repos/{repo_name}/issues/comments/{comment_id}", headers=headers
        )

    def update_issue_comment(
        self,
        repo_name: str,
        comment_id: int,
        body: str,
        accept: str = "application/vnd.github+json",
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
        return self._make_request(
            "PATCH",
            f"/repos/{repo_name}/issues/comments/{comment_id}",
            headers=headers,
            data=data,
        )

    def delete_issue_comment(
        self,
        repo_name: str,
        comment_id: int,
        accept: str = "application/vnd.github+json",
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
        self._make_request(
            "DELETE",
            f"/repos/{repo_name}/issues/comments/{comment_id}",
            headers=headers,
        )

    def create_issue_comment(
        self,
        repo_name: str,
        issue_number: int,
        body: str,
        accept: str = "application/vnd.github+json",
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
        return self._make_request(
            "POST",
            f"/repos/{repo_name}/issues/{issue_number}/comments",
            headers=headers,
            data=data,
        )

    def create_pull_request(
        self, repo_name: str, title: str, body: str, head: str, base: str
    ) -> Dict:
        """Create a pull request."""
        data = {"title": title, "body": body, "head": head, "base": base}
        return self._make_request("POST", f"/repos/{repo_name}/pulls", data)

    def list_pull_requests(
        self, 
        repo_name: str, 
        state: str = "open", 
        sort: str = "created", 
        direction: str = "desc", 
        per_page: int = 30, 
        page: int = 1,
    ) -> Dict:
        """List pull requests for a repository."""
        params = {"state": state, "sort": sort, "direction": direction, "per_page": per_page, "page": page}
        return self._make_request("GET", f"/repos/{repo_name}/pulls", params=params)

    def list_assignees(
        self,
        repo_name: str,
        per_page: int = 30,
        page: int = 1,
        accept: str = "application/vnd.github+json",
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
        params = {"per_page": per_page, "page": page}
        return self._make_request(
            "GET", f"/repos/{repo_name}/assignees", headers=headers, params=params
        )

    def check_assignee(
        self, repo_name: str, assignee: str, accept: str = "application/vnd.github+json"
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
            self._make_request(
                "GET", f"/repos/{repo_name}/assignees/{assignee}", headers=headers
            )
            return True
        except IntegrationConnectionError:
            return False

    def add_assignees_to_issue(
        self,
        repo_name: str,
        issue_number: int,
        assignees: List[str],
        accept: str = "application/vnd.github+json",
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
            data=data,
        )

    def remove_assignees_from_issue(
        self,
        repo_name: str,
        issue_number: int,
        assignees: List[str],
        accept: str = "application/vnd.github+json",
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
            data=data,
        )

    def check_assignee_permission(
        self,
        repo_name: str,
        issue_number: int,
        assignee: str,
        accept: str = "application/vnd.github+json",
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
                headers=headers,
            )
            return True
        except IntegrationConnectionError:
            return False

    def get_repository_public_key(
        self,
        repo_name: str,
    ) -> Dict:
        """Gets the public key needed to encrypt secrets for a repository.

        Args:
            repo_name (str): Repository name in 'owner/repo' format

        Returns:
            Dict: Response containing:
                - key_id (str): The identifier for the key
                - key (str): The Base64 encoded public key

        Note:
            - Anyone with read access to the repository can use this endpoint
            - For private repos, OAuth tokens need repo scope
            - Fine-grained tokens need "Secrets" repository read permissions
        """
        return self._make_request(
            "GET", f"/repos/{repo_name}/actions/secrets/public-key"
        )

    def list_repository_secrets(
        self,
        repo_name: str,
    ) -> Dict:
        """Lists all secrets available in a repository without revealing their encrypted values.

        Args:
            repo_name (str): Repository name in 'owner/repo' format

        Returns:
            Dict: Response containing:
                - total_count (int): Total number of secrets
                - secrets (List[Dict]): List of secrets with name, created_at and updated_at

        Note:
            Requires collaborator access to repository.
            OAuth tokens need repo scope.
            Fine-grained tokens need "Secrets" repository read permissions.
        """
        return self._make_request("GET", f"/repos/{repo_name}/actions/secrets")

    def get_repository_secret(
        self,
        repo_name: str,
        secret_name: str,
    ) -> Dict:
        """Get a repository secret."""
        return self._make_request(
            "GET", f"/repos/{repo_name}/actions/secrets/{secret_name}"
        )

    def create_or_update_repository_secret(
        self,
        repo_name: str,
        secret_name: str,
        value: str,
    ) -> Dict:
        """Creates or updates a repository secret with an encrypted value.

        Args:
            repo_name (str): Repository name in 'owner/repo' format
            secret_name (str): Name of the secret
            value (str): Plain text value that will be encrypted with LibSodium using the repository public key

        Returns:
            Dict: Response data from creating/updating the secret

        Note:
            - Requires collaborator access to repository
            - OAuth tokens need repo scope
            - Fine-grained tokens need "Secrets" repository write permissions
        """
        from base64 import b64decode
        import nacl.encoding
        from nacl.public import PublicKey, SealedBox

        # Get repository public key
        public_key_response = self.get_repository_public_key(repo_name)
        public_key = public_key_response["key"]
        key_id = public_key_response["key_id"]

        # Encrypt value using LibSodium
        public_key_bytes = b64decode(public_key)
        sealed_box = SealedBox(PublicKey(public_key_bytes))
        encrypted_value = sealed_box.encrypt(value.encode("utf-8"))
        encrypted_value_b64 = nacl.encoding.Base64Encoder.encode(
            encrypted_value
        ).decode("utf-8")

        data = {"encrypted_value": encrypted_value_b64, "key_id": key_id}
        return self._make_request(
            "PUT", f"/repos/{repo_name}/actions/secrets/{secret_name}", data=data
        )

    def delete_repository_secret(
        self,
        repo_name: str,
        secret_name: str,
    ) -> None:
        """Deletes a secret from a repository.

        Args:
            repo_name (str): Repository name in 'owner/repo' format
            secret_name (str): Name of the secret to delete

        Returns:
            None

        Note:
            - Requires collaborator access to repository
            - OAuth tokens need repo scope
            - Fine-grained tokens need "Secrets" repository write permissions
        """
        self._make_request(
            "DELETE", f"/repos/{repo_name}/actions/secrets/{secret_name}"
        )

    def list_repository_contributors(
        self,
        repo_name: str,
        page: int = 1,
        per_page: int = 30,
        return_login: bool = False,
    ) -> List | Dict:
        """Lists contributors to a repository.

        Args:
            repo_name (str): Repository name in 'owner/repo' format
            anon (bool, optional): Include anonymous contributors. Defaults to False.
            per_page (int, optional): Results per page. Defaults to 30.
            page (int, optional): Page number of results. Defaults to 1.
            return_login (bool, optional): Return only login names of contributors. Defaults to False.
            accept (str, optional): Media type for response format. Defaults to "application/vnd.github+json"

        Returns:
            Dict: List of contributors to the repository, including:
                - Login
                - ID
                - Node ID
                - Avatar URL
                - URL
                - Type
                - Contributions count
                - And more

        Note:
            Lists contributors to the specified repository, sorted by number of commits per contributor in descending order.
        """
        params = {
            "per_page": per_page,
            "page": page
        }
        response = self._make_request(
            "GET",
            f"/repos/{repo_name}/contributors",
            params=params
        )
        
        if return_login:
            return [{'login': c.get('login'), "contributions": c.get('contributions')} for c in response if c.get('type') == 'User' and c.get('login')]
        return response



def as_tools(configuration: GitHubIntegrationConfiguration):
    from langchain_core.tools import StructuredTool

    integration: GitHubIntegration = GitHubIntegration(configuration)

    class GetUserDetailsSchema(BaseModel):
        username: str = Field(
            ..., description="GitHub username of the user to fetch details for"
        )

    class CreateUserRepositorySchema(BaseModel):
        name: str = Field(..., description="Name of the repository to create")
        private: bool = Field(
            ..., description="Whether the repository should be private"
        )
        description: str = Field(..., description="Description of the repository")

    class GetRepositorySchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )

    class ListOrganizationRepositoriesSchema(BaseModel):
        org: str = Field(..., description="GitHub organization name")

    class CreateOrganizationRepositorySchema(BaseModel):
        org: str = Field(..., description="GitHub organization name")
        name: str = Field(..., description="Name of the repository to create")
        private: bool = Field(
            ..., description="Whether the repository should be private"
        )
        description: str = Field(..., description="Description of the repository")

    class UpdateOrganizationRepositorySchema(BaseModel):
        org: str = Field(..., description="GitHub organization name")
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        data: Dict = Field(..., description="Data to update the repository with")

    class DeleteOrganizationRepositorySchema(BaseModel):
        org: str = Field(..., description="GitHub organization name")
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )

    class ListRepositoryActivitiesSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )

    class GetRepositoryContributorsSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )

    class CreateIssueSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        title: str = Field(..., description="Title of the issue")
        body: str = Field(..., description="Body of the issue")
        labels: List[str] = Field(..., description="Labels to apply to the issue")
        assignees: List[str] = Field(
            ..., description="Assignees to assign to the issue"
        )

    class GetIssueSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        issue_id: str = Field(..., description="ID of the issue to fetch")

    class GetIssuesSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        filter: str = Field(
            ...,
            description="Filter issues by: assigned, created, mentioned, subscribed, repos, all",
        )
        state: str = Field(..., description="Filter issues by state: open, closed, all")
        sort: str = Field(..., description="Sort issues by: created, updated, comments")
        direction: str = Field(..., description="Sort direction: asc, desc")
        limit: int = Field(..., description="Maximum number of issues to return")
        since: str = Field(
            ...,
            description="Only show results updated after timestamp (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)",
        )
        labels: str = Field(
            ...,
            description="Comma-separated list of label names. Example: 'bug,ui,@high'",
        )

    class ListIssueCommentsSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        sort: str = Field(
            ..., description="Property to sort results by: created, updated"
        )
        direction: str = Field(..., description="Sort direction: asc, desc")
        since: str = Field(
            ...,
            description="Only show results updated after timestamp (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)",
        )
        per_page: int = Field(..., description="Number of results per page (max 100)")
        page: int = Field(..., description="Page number of results to fetch")

    class GetIssueCommentSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        comment_id: int = Field(..., description="ID of the comment to fetch")

    class UpdateIssueCommentSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        comment_id: int = Field(..., description="ID of the comment to update")
        body: str = Field(..., description="New body of the comment")

    class DeleteIssueCommentSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        comment_id: int = Field(..., description="ID of the comment to delete")

    class CreateIssueCommentSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        issue_number: int = Field(..., description="ID of the issue to comment on")
        body: str = Field(..., description="Body of the comment")

    class CreatePullRequestSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        title: str = Field(..., description="Title of the pull request")
        body: str = Field(..., description="Body of the pull request")
        head: str = Field(..., description="Branch to merge into base")
        base: str = Field(..., description="Base branch to merge from")

    class ListAssigneesSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )

    class CheckAssigneePermissionSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        issue_number: int = Field(
            ..., description="ID of the issue to check assignee permission for"
        )
        assignee: str = Field(..., description="Username of the assignee to check")

    class AddAssigneesToIssueSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        issue_number: int = Field(
            ..., description="ID of the issue to add assignees to"
        )
        assignees: List[str] = Field(
            ..., description="Usernames of people to assign this issue to"
        )

    class RemoveAssigneesFromIssueSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        issue_number: int = Field(
            ..., description="ID of the issue to remove assignees from"
        )
        assignees: List[str] = Field(
            ..., description="Usernames of assignees to remove from the issue"
        )

    class ListRepositorySecretsSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )

    class GetRepositorySecretSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        secret_name: str = Field(..., description="Name of the secret")

    class CreateOrUpdateRepositorySecretSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        secret_name: str = Field(..., description="Name of the secret")
        value: str = Field(..., description="Value for the secret")

    class DeleteRepositorySecretSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )
        secret_name: str = Field(..., description="Name of the secret to delete")

    class ListRepositoryContributorsSchema(BaseModel):
        repo_name: str = Field(
            ..., description="Full repository name in format 'owner/repo'"
        )

    return [
        StructuredTool(
            name="github_get_user_details",
            description="Get details about a GitHub user",
            func=lambda username: integration.get_user_details(username),
            args_schema=GetUserDetailsSchema,
        ),
        StructuredTool(
            name="github_create_user_repository",
            description="Create a new repository for the user",
            func=lambda name, private, description: integration.create_user_repository(
                name, private, description
            ),
            args_schema=CreateUserRepositorySchema,
        ),
        StructuredTool(
            name="github_get_repository_details",
            description="Get details about a GitHub repository",
            func=lambda repo_name: integration.get_repository_details(repo_name),
            args_schema=GetRepositorySchema,
        ),
        StructuredTool(
            name="github_list_organization_repositories",
            description="Lists repositories for the specified organization in GitHub",
            func=lambda org: integration.list_organization_repositories(org, return_list=True),
            args_schema=ListOrganizationRepositoriesSchema,
        ),
        StructuredTool(
            name="github_create_organization_repository",
            description="Create a new repository for an organization",
            func=lambda org,
            name,
            private,
            description: integration.create_organization_repository(
                org, name, private, description
            ),
            args_schema=CreateOrganizationRepositorySchema,
        ),
        StructuredTool(
            name="github_update_organization_repository",
            description="Update a repository for an organization",
            func=lambda org,
            repo_name,
            data: integration.update_organization_repository(org, repo_name, data),
            args_schema=UpdateOrganizationRepositorySchema,
        ),
        StructuredTool(
            name="github_delete_organization_repository",
            description="Delete a repository for an organization",
            func=lambda org, repo_name: integration.delete_repository(
                org, repo_name
            ),
            args_schema=DeleteOrganizationRepositorySchema,
        ),
        StructuredTool(
            name="github_list_repository_activities",
            description="Get a list of activities for the specified repository",
            func=lambda repo_name: integration.list_repository_activities(repo_name),
            args_schema=ListRepositoryActivitiesSchema,
        ),
        StructuredTool(
            name="github_get_repository_contributors",
            description="Get a list of contributors for the specified repository",
            func=lambda repo_name: integration.get_repository_contributors(repo_name),
            args_schema=GetRepositoryContributorsSchema,
        ),
        StructuredTool(
            name="github_create_issue",
            description="Create an issue in the specified repository",
            func=lambda repo_name,
            title,
            body,
            labels,
            assignees: integration.create_issue(
                repo_name, title, body, labels, assignees
            ),
            args_schema=CreateIssueSchema,
        ),
        StructuredTool(
            name="github_get_issue",
            description="Get an issue from a repository",
            func=lambda repo_name, issue_id: integration.get_issue(repo_name, issue_id),
            args_schema=GetIssueSchema,
        ),
        StructuredTool(
            name="github_list_issues",
            description="Get issues from a repository",
            func=lambda repo_name,
            filter,
            state,
            sort,
            direction,
            limit,
            since,
            labels: integration.list_issues(
                repo_name, filter, state, sort, direction, limit, since, labels
            ),
            args_schema=GetIssuesSchema,
        ),
        StructuredTool(
            name="github_list_issue_comments",
            description="Get comments on an issue or pull request",
            func=lambda repo_name,
            sort,
            direction,
            since,
            per_page,
            page: integration.list_issue_comments(
                repo_name, sort, direction, since, per_page, page
            ),
            args_schema=ListIssueCommentsSchema,
        ),
        StructuredTool(
            name="github_get_issue_comment",
            description="Get a comment on an issue or pull request",
            func=lambda repo_name, comment_id: integration.get_issue_comment(
                repo_name, comment_id
            ),
            args_schema=GetIssueCommentSchema,
        ),
        StructuredTool(
            name="github_update_issue_comment",
            description="Update a comment on an issue or pull request",
            func=lambda repo_name, comment_id, body: integration.update_issue_comment(
                repo_name, comment_id, body
            ),
            args_schema=UpdateIssueCommentSchema,
        ),
        StructuredTool(
            name="github_delete_issue_comment",
            description="Delete a comment on an issue or pull request",
            func=lambda repo_name, comment_id: integration.delete_issue_comment(
                repo_name, comment_id
            ),
            args_schema=DeleteIssueCommentSchema,
        ),
        StructuredTool(
            name="github_create_issue_comment",
            description="Create a comment on an issue or pull request",
            func=lambda repo_name, issue_number, body: integration.create_issue_comment(
                repo_name, issue_number, body
            ),
            args_schema=CreateIssueCommentSchema,
        ),
        StructuredTool(
            name="github_create_pull_request",
            description="Create a pull request in the specified repository",
            func=lambda repo_name,
            title,
            body,
            head,
            base: integration.create_pull_request(repo_name, title, body, head, base),
            args_schema=CreatePullRequestSchema,
        ),
        StructuredTool(
            name="github_list_assignees",
            description="Get a list of assignees for the specified repository",
            func=lambda repo_name: integration.list_assignees(repo_name),
            args_schema=ListAssigneesSchema,
        ),
        StructuredTool(
            name="github_check_assignee_permission",
            description="Check if a user can be assigned to a specific issue",
            func=lambda repo_name,
            issue_number,
            assignee: integration.check_assignee_permission(
                repo_name, issue_number, assignee
            ),
            args_schema=CheckAssigneePermissionSchema,
        ),
        StructuredTool(
            name="github_add_assignees_to_issue",
            description="Add assignees to an issue",
            func=lambda repo_name,
            issue_number,
            assignees: integration.add_assignees_to_issue(
                repo_name, issue_number, assignees
            ),
            args_schema=AddAssigneesToIssueSchema,
        ),
        StructuredTool(
            name="github_remove_assignees_from_issue",
            description="Remove assignees from an issue",
            func=lambda repo_name,
            issue_number,
            assignees: integration.remove_assignees_from_issue(
                repo_name, issue_number, assignees
            ),
            args_schema=RemoveAssigneesFromIssueSchema,
        ),
        StructuredTool(
            name="github_list_repository_secrets",
            description="List all secrets available in a GitHub repository without revealing their encrypted values",
            func=lambda repo_name: integration.list_repository_secrets(repo_name),
            args_schema=ListRepositorySecretsSchema,
        ),
        StructuredTool(
            name="github_get_repository_secret",
            description="Get a secret from a GitHub repository",
            func=lambda repo_name, secret_name: integration.get_repository_secret(
                repo_name, secret_name
            ),
            args_schema=GetRepositorySecretSchema,
        ),
        StructuredTool(
            name="github_create_or_update_repository_secret",
            description="Create or update a secret in a GitHub repository",
            func=lambda repo_name,
            secret_name,
            value: integration.create_or_update_repository_secret(
                repo_name, secret_name, value
            ),
            args_schema=CreateOrUpdateRepositorySecretSchema,
        ),
        StructuredTool(
            name="github_delete_repository_secret",
            description="Delete a secret from a GitHub repository",
            func=lambda repo_name, secret_name: integration.delete_repository_secret(
                repo_name, secret_name
            ),
            args_schema=DeleteRepositorySecretSchema,
        ),
        StructuredTool(
            name="github_list_repository_contributors",
            description="List contributors to a GitHub repository",
            func=lambda repo_name: integration.list_repository_contributors(repo_name, return_login=True),
            args_schema=ListRepositoryContributorsSchema,
        ),
    ]
