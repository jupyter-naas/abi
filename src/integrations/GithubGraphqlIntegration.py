from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from dataclasses import dataclass
import requests
from typing import Dict, Any, Optional

LOGO_URL = "https://logo.clearbit.com/github.com"

@dataclass
class GithubGraphqlIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Github GraphQL integration.
    
    Attributes:
        access_token (str): Github personal access token for authentication
        api_url (str): GraphQL API endpoint, defaults to https://api.github.com/graphql
    """
    access_token: str
    api_url: str = "https://api.github.com/graphql"

class GithubGraphqlIntegration(Integration):
    """Github GraphQL API integration class.
    
    This integration provides methods to interact with Github's GraphQL API endpoints.
    """

    __configuration: GithubGraphqlIntegrationConfiguration

    def __init__(self, configuration: GithubGraphqlIntegrationConfiguration):
        """Initialize Github GraphQL client with access token."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Content-Type": "application/json"
        }

    def execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against Github's API.
        
        Args:
            query (str): The GraphQL query to execute
            variables (Dict, optional): Variables for the GraphQL query
            
        Returns:
            Dict[str, Any]: The query response data
            
        Raises:
            IntegrationConnectionError: If the API request fails
        """
        try:
            response = requests.post(
                self.__configuration.api_url,
                headers=self.headers,
                json={"query": query, "variables": variables}
            )
            response.raise_for_status()
            result = response.json()
            
            if "errors" in result:
                raise IntegrationConnectionError(f"GraphQL query failed: {result['errors']}")
            
            return result
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Github GraphQL API request failed: {str(e)}")

    def get_project_node_id(self, organization: str, number: int) -> str:
        """Get the node ID of an organization project.
        
        Args:
            organization (str): The organization login name
            number (int): The project number
            
        Returns:
            str: The project node ID
        """
        query = """
        query($org: String!, $number: Int!) {
            organization(login: $org) {
                projectV2(number: $number) {
                    id
                }
            }
        }
        """
        variables = {
            "org": organization,
            "number": int(number)
        }
        return self.execute_query(query, variables)
    
    def get_project_details(self, project_node_id: str) -> Dict[str, Any]:
        """Get detailed information about a GitHub Project.
        
        Args:
            project_node_id (str): The node ID of the GitHub Project
            
        Returns:
            Dict[str, Any]: Response containing project details including:
                - Basic project info (title, number, url)
                - Fields configuration
                - Items count
            
        Raises:
            IntegrationConnectionError: If the API request fails
        """
        query = """
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    id
                    title
                    number
                    url
                    shortDescription
                    public
                    closed
                    items(first: 0) {
                        totalCount
                    }
                    fields(first: 20) {
                        nodes {
                            ... on ProjectV2Field {
                                id
                                name
                                dataType
                            }
                            ... on ProjectV2IterationField {
                                id
                                name
                                configuration {
                                    iterations {
                                        id
                                        title
                                        duration
                                        startDate
                                    }
                                }
                            }
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                options {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "projectId": project_node_id
        }
        return self.execute_query(query, variables)
    
    def get_project_fields(self, project_id: str):
        """Get information about project fields in a GitHub Project.

        Args:
            project_id (str): The node ID of the GitHub Project

        Returns:
            dict: Response containing project field information including:
                - Regular fields with id and name
                - Iteration fields with id, name and iteration configuration
                - Single select fields with id, name and options
        """
        query = """
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    fields(first: 20) {
                        nodes {
                            ... on ProjectV2Field {
                                id
                                name
                            }
                            ... on ProjectV2IterationField {
                                id
                                name
                                configuration {
                                    iterations {
                                        startDate
                                        id
                                    }
                                }
                            }
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                options {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "projectId": project_id
        }
        return self.execute_query(query, variables)
    
    def get_item_id_from_node_id(self, node_id: str) -> Dict[str, Any]:
        """Retrieves a project item ID from a node ID using the GitHub GraphQL API.
        
        Args:
            node_id (str): The Node ID to look up
            
        Returns:
            Dict[str, Any]: Response data containing the project item information
            
        Raises:
            IntegrationConnectionError: If the API request fails
        """
        query = """
        query GetProjectItemFromNode($nodeId: ID!) {
            node(id: $nodeId) {
                ... on Issue {
                    projectItems(first: 1) {
                        nodes {
                            id
                            project {
                                id
                                title
                                number
                            }
                        }
                    }
                }
                ... on PullRequest {
                    projectItems(first: 1) {
                        nodes {
                            id
                            project {
                                id
                                title
                                number
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "nodeId": node_id
        }
        return self.execute_query(query, variables)
    
    def get_item_details(self, item_id: str) -> Dict[str, Any]:
        """Retrieves a project item using its ID from the GitHub GraphQL API.
        
        Args:
            item_id (str): The Node ID of the project item
            
        Returns:
            Dict[str, Any]: Response data containing the project item details
            
        Raises:
            IntegrationConnectionError: If the API request fails
        """
        query = """
        query GetProjectItem($itemId: ID!) {
            node(id: $itemId) {
                ... on ProjectV2Item {
                    id
                    type
                    fieldValues(first: 20) {
                        nodes {
                            ... on ProjectV2ItemFieldTextValue {
                                text
                                field {
                                    ... on ProjectV2FieldCommon {
                                        name
                                    }
                                }
                            }
                            ... on ProjectV2ItemFieldDateValue {
                                date
                                field {
                                    ... on ProjectV2FieldCommon {
                                        name
                                    }
                                }
                            }
                            ... on ProjectV2ItemFieldSingleSelectValue {
                                name
                                field {
                                    ... on ProjectV2FieldCommon {
                                        name
                                    }
                                }
                            }
                            ... on ProjectV2ItemFieldNumberValue {
                                number
                                field {
                                    ... on ProjectV2FieldCommon {
                                        name
                                    }
                                }
                            }
                            ... on ProjectV2ItemFieldIterationValue {
                                title
                                startDate
                                duration
                                field {
                                    ... on ProjectV2FieldCommon {
                                        name
                                    }
                                }
                            }
                            ... on ProjectV2ItemFieldMilestoneValue {
                                milestone {
                                    title
                                    dueOn
                                }
                                field {
                                    ... on ProjectV2FieldCommon {
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "itemId": item_id
        }
        return self.execute_query(query, variables)
    
    def add_issue_to_project(self, project_node_id: str, issue_node_id: str, status_field_id: Optional[str] = None, priority_field_id: Optional[str] = None, status_option_id: Optional[str] = None, priority_option_id: Optional[str] = None) -> dict:
        """
        Associates an issue with a project using the GitHub GraphQL API and sets the status and priority fields.
        
        Args:
            project_node_id (str): The Node ID of the project (ProjectV2)
            issue_node_id (str): The Node ID of the issue
            status_field_id (str): The field ID for status (e.g., "PVTSSF_lADOBESWNM4AKRt3zgGZRV8")
            priority_field_id (str): The field ID for priority (e.g., "PVTSSF_lADOBESWNM4AKRt3zgGac0g")
            status_option_id (str): The option ID for status (e.g., "97363483" for "📥Inbox")
            priority_option_id (str): The option ID for priority (e.g., "82a23910" for "Urgent")
            
        Returns:
            dict: Response data from the API
        """
        # First mutation: Add issue to project
        add_mutation = """
        mutation AddIssueToProject($projectId: ID!, $issueId: ID!) {
            addProjectV2ItemById(input: {
                projectId: $projectId
                contentId: $issueId
            }) {
                item {
                    id
                }
            }
        }
        """

        # Add issue to project
        variables = {
            "projectId": project_node_id,
            "issueId": issue_node_id
        }
        
        data = self.execute_query(add_mutation, variables)

        # Get the item ID from the response
        item_id = data['data']["addProjectV2ItemById"]["item"]["id"]

        # Update status field if provided
        if status_field_id and status_option_id:
            status_mutation = """
            mutation UpdateStatus($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
                updateProjectV2ItemFieldValue(input: {
                    projectId: $projectId
                    itemId: $itemId
                    fieldId: $fieldId
                    value: { singleSelectOptionId: $optionId }
                }) {
                    projectV2Item {
                        id
                    }
                }
            }
            """
            variables = {
                "projectId": project_node_id,
                "itemId": item_id,
                "fieldId": status_field_id,
                "optionId": status_option_id
            }
            data = self.execute_query(status_mutation, variables)

        # Update priority field if provided
        if priority_field_id and priority_option_id:
            priority_mutation = """
            mutation UpdatePriority($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
                updateProjectV2ItemFieldValue(input: {
                    projectId: $projectId
                    itemId: $itemId
                    fieldId: $fieldId
                    value: { singleSelectOptionId: $optionId }
                }) {
                    projectV2Item {
                        id
                    }
                }
            }
            """
            variables = {
                "projectId": project_node_id,
                "itemId": item_id,
                "fieldId": priority_field_id,
                "optionId": priority_option_id
            }
            data = self.execute_query(priority_mutation, variables)

        return data

def as_tools(configuration: GithubGraphqlIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Optional
    
    integration = GithubGraphqlIntegration(configuration)
    
    class GetProjectNodeIdSchema(BaseModel):
        organization: str = Field(..., description="The organization login name")
        number: int = Field(..., description="The project number")

    class GetProjectDetailsSchema(BaseModel):
        project_node_id: str = Field(..., description="The Node ID of the GitHub Project")     

    return [
        StructuredTool(
            name="get_github_project_node_id",
            description="Get the node ID of an organization project in GitHub from its number.",
            func=lambda organization, number: integration.get_project_node_id(organization, number),
            args_schema=GetProjectNodeIdSchema
        ),
        StructuredTool(
            name="get_github_project_details",
            description="Get detailed information about a GitHub Project including fields configuration and items count from its node ID.",
            func=lambda project_node_id: integration.get_project_details(project_node_id),
            args_schema=GetProjectDetailsSchema
        ),
    ]