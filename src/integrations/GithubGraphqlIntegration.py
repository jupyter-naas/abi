from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from dataclasses import dataclass
import requests
from typing import Dict, Any, Optional

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
    
    This class provides methods to interact with Github's GraphQL API endpoints.
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
        
        # Test connection
        try:
            self.execute_query("""
                query { 
                    viewer { 
                        login 
                    } 
                }
            """)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to connect to Github GraphQL API: {str(e)}")

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
            
            return result["data"]
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Github GraphQL API request failed: {str(e)}")

    def find_org_project_node_id(self, organization: str, number: int) -> str:
        """Find the node ID of an organization project.
        
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
            "number": number
        }
        return self.execute_query(query, variables)
    
    def get_project_item_from_node(self, node_id: str) -> Dict[str, Any]:
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
    
    def get_project_item_by_id(self, item_id: str) -> Dict[str, Any]:
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
    
    def find_project_fields(self, project_id: str):
        """Find information about project fields in a GitHub Project.

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
    
    def add_issue_to_project(self, project_id: str, issue_id: str, status_field_id: str, priority_field_id: str, status_option_id: str, priority_option_id: str) -> dict:
        """
        Associates an issue with a project using the GitHub GraphQL API and sets the status and priority fields.
        
        Args:
            project_id (str): The Node ID of the project (ProjectV2)
            issue_id (str): The Node ID of the issue
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
            "projectId": project_id,
            "issueId": issue_id
        }
        
        data = self.execute_query(add_mutation, variables)
        
        # Get the item ID from the response
        item_id = data["addProjectV2ItemById"]["item"]["id"]

        # Update fields mutation
        update_mutation = """
        mutation UpdateFields($projectId: ID!, $itemId: ID!, $statusFieldId: ID!, $priorityFieldId: ID!, $statusOptionId: String!, $priorityOptionId: String!) {
            updateStatus: updateProjectV2ItemFieldValue(input: {
                projectId: $projectId
                itemId: $itemId
                fieldId: $statusFieldId
                value: { singleSelectOptionId: $statusOptionId }
            }) {
                projectV2Item {
                    id
                }
            }
            updatePriority: updateProjectV2ItemFieldValue(input: {
                projectId: $projectId
                itemId: $itemId
                fieldId: $priorityFieldId
                value: { singleSelectOptionId: $priorityOptionId }
            }) {
                projectV2Item {
                    id
                }
            }
        }
        """

        # Update the fields
        variables = {
            "projectId": project_id,
            "itemId": item_id,
            "statusFieldId": status_field_id,
            "priorityFieldId": priority_field_id,
            "statusOptionId": status_option_id,
            "priorityOptionId": priority_option_id
        }
        
        return self.execute_query(update_mutation, variables)
    
def as_tools(configuration: GithubGraphqlIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = GithubGraphqlIntegration(configuration)
    
    class FindOrgProjectNodeIdSchema(BaseModel):
        organization: str = Field(..., description="The organization login name")
        number: int = Field(..., description="The project number")
        
    class GetProjectItemFromNodeSchema(BaseModel):
        node_id: str = Field(..., description="The Node ID to look up")

    class GetProjectItemByIdSchema(BaseModel):
        item_id: str = Field(..., description="The Node ID of the project item")

    class AddIssueToProjectSchema(BaseModel):
        project_id: str = Field(..., description="The Node ID of the project (ProjectV2)")
        issue_id: str = Field(..., description="The Node ID of the issue")
        status_field_id: Optional[str] = Field(None, description="The field ID for status")
        priority_field_id: Optional[str] = Field(None, description="The field ID for priority")
        status_option_id: Optional[str] = Field(None, description="The option ID for status")
        priority_option_id: Optional[str] = Field(None, description="The option ID for priority")
        
    return [
        StructuredTool(
            name="find_github_org_project_node_id",
            description="Find the node ID of an organization project in GitHub",
            func=lambda organization, number: integration.find_org_project_node_id(organization, number),
            args_schema=FindOrgProjectNodeIdSchema
        ),
        StructuredTool(
            name="get_github_project_item_from_node",
            description="Retrieves a project item ID from a node ID using the GitHub GraphQL API",
            func=lambda node_id: integration.get_project_item_from_node(node_id),
            args_schema=GetProjectItemFromNodeSchema
        ),
        StructuredTool(
            name="get_github_project_item_by_id",
            description="Retrieves a project item using its ID from the GitHub GraphQL API",
            func=lambda item_id: integration.get_project_item_by_id(item_id),
            args_schema=GetProjectItemByIdSchema
        ),
        StructuredTool(
            name="add_github_issue_to_project",
            description="Associates an issue with a project using the GitHub GraphQL API and sets the status and priority fields",
            func=lambda project_id, issue_id, status_field_id, priority_field_id, status_option_id, priority_option_id: integration.add_issue_to_project(project_id, issue_id, status_field_id, priority_field_id, status_option_id, priority_option_id),
            args_schema=AddIssueToProjectSchema
        )
    ]
    
    