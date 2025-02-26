# Pipelines

This document explains the concept of Pipelines in the ABI framework, their purpose, implementation, and how they process and transform data from external systems into the knowledge graph.

## What are Pipelines?

Pipelines are data processing components that extract data from external systems via integrations, transform the data into a semantic representation, and load it into the ontology store. They implement the Extract-Transform-Load (ETL) pattern within the ABI architecture.

## Key Features

- **Data Extraction**: Use integrations to fetch data from external sources
- **Data Transformation**: Convert domain-specific data into semantic graph representations
- **Knowledge Graph Population**: Add entities and relationships to the ontology store
- **Incremental Processing**: Support for processing only new or changed data
- **Validation**: Ensure data quality and consistency with the ontology schema
- **Error Handling**: Gracefully handle and report data processing errors

## Pipeline Architecture

```
┌───────────────────────────────────────────────────────────┐
│                        Pipeline                           │
│                                                           │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────┐  │
│  │  Data         │    │  Data         │    │  Graph    │  │
│  │  Extractor    │───►│  Transformer  │───►│  Builder  │  │
│  │               │    │               │    │           │  │
│  └───────────────┘    └───────────────┘    └───────────┘  │
│          ▲                                       │        │
│          │                                       ▼        │
│  ┌───────────────┐                        ┌───────────┐   │
│  │  Integration  │                        │ Ontology  │   │
│  │  Layer        │                        │ Store     │   │
│  │               │                        │           │   │
│  └───────────────┘                        └───────────┘   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Pipeline Components

### Configuration

Defines the pipeline's behavior, including which integrations to use and how to connect to the ontology store:

```python
@dataclass
class SalesDataPipelineConfiguration(PipelineConfiguration):
    """Configuration for the Sales Data Pipeline.
    
    Attributes:
        salesforce_integration (SalesforceIntegration): The Salesforce integration to use
        ontology_store (IOntologyStoreService): The ontology store service
        ontology_store_name (str): Name of the ontology store to use
    """
    salesforce_integration: SalesforceIntegration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "sales_ontology"
```

### Parameters

Runtime parameters that control the pipeline's execution:

```python
class SalesDataPipelineParameters(PipelineParameters):
    """Parameters for the Sales Data Pipeline.
    
    Attributes:
        start_date (str): Start date for data extraction (ISO format)
        end_date (str): End date for data extraction (ISO format)
        include_opportunities (bool): Whether to include opportunity data
    """
    start_date: str
    end_date: str
    include_opportunities: bool = True
```

### Data Extraction

Methods that use integrations to extract data from external systems:

```python
def _extract_accounts(self, parameters: SalesDataPipelineParameters) -> List[Dict]:
    """Extract account data from Salesforce.
    
    Args:
        parameters: Pipeline parameters with date range
        
    Returns:
        List of account records
    """
    query = f"""
        SELECT Id, Name, Industry, BillingCity, BillingCountry
        FROM Account
        WHERE LastModifiedDate >= {parameters.start_date}
        AND LastModifiedDate <= {parameters.end_date}
    """
    return self.__configuration.salesforce_integration.query(query)
```

### Data Transformation

Methods that transform extracted data into semantic representations:

```python
def _transform_account(self, account_data: Dict) -> None:
    """Transform a Salesforce account into graph entities and relationships.
    
    Args:
        account_data: Raw account data from Salesforce
    """
    # Create a company entity
    company_uri = self.__graph.create_entity(
        "Company",
        {
            "id": account_data["Id"],
            "name": account_data["Name"],
            "industry": account_data.get("Industry", "Unknown")
        }
    )
    
    # Create a location entity if billing information exists
    if account_data.get("BillingCity") and account_data.get("BillingCountry"):
        location_uri = self.__graph.create_entity(
            "Location",
            {
                "city": account_data["BillingCity"],
                "country": account_data["BillingCountry"]
            }
        )
        
        # Link company to location
        self.__graph.create_relationship(
            company_uri,
            "hasHeadquarters",
            location_uri
        )
```

### Graph Building

Methods that assemble the complete knowledge graph:

```python
def _build_graph(self, accounts: List[Dict], opportunities: List[Dict]) -> None:
    """Build the complete knowledge graph from transformed data.
    
    Args:
        accounts: List of account records
        opportunities: List of opportunity records
    """
    # Process all accounts
    for account in accounts:
        self._transform_account(account)
    
    # Process all opportunities if requested
    if self.__parameters.include_opportunities:
        for opportunity in opportunities:
            self._transform_opportunity(opportunity)
    
    # Add metadata about the pipeline run
    self.__graph.add_metadata({
        "pipeline": "SalesDataPipeline",
        "execution_time": datetime.now().isoformat(),
        "record_count": len(accounts) + len(opportunities)
    })
```

## Creating a Pipeline

A simplified example of creating a custom pipeline:

```python
from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.integrations import JiraIntegration
from abi.utils.Graph import ABIGraph
from rdflib import Graph
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

@dataclass
class JiraTicketPipelineConfiguration(PipelineConfiguration):
    """Configuration for JiraTicketPipeline.
    
    Attributes:
        jira_integration (JiraIntegration): The Jira integration to use
        ontology_store (IOntologyStoreService): The ontology store service
        ontology_store_name (str): Name of the ontology store to use
    """
    jira_integration: JiraIntegration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "project_ontology"

class JiraTicketPipelineParameters(PipelineParameters):
    """Parameters for JiraTicketPipeline execution.
    
    Attributes:
        project_key (str): Jira project key (e.g., 'ABI')
        max_issues (int): Maximum number of issues to process
    """
    project_key: str
    max_issues: int = 100

class JiraTicketPipeline(Pipeline):
    """Pipeline for extracting Jira tickets and loading them into the ontology store."""
    
    __configuration: JiraTicketPipelineConfiguration
    
    def __init__(self, configuration: JiraTicketPipelineConfiguration):
        self.__configuration = configuration
        
    def run(self, parameters: JiraTicketPipelineParameters) -> Graph:
        # Create a new graph
        graph = ABIGraph()
        
        # Query Jira for issues in the specified project
        jql_query = f"project = {parameters.project_key} ORDER BY created DESC"
        issues = self.__configuration.jira_integration.search_issues(
            jql_query, 
            max_results=parameters.max_issues
        )
        
        # Transform issues into semantic entities
        for issue in issues:
            # Create issue entity
            issue_uri = graph.create_entity(
                "Issue",
                {
                    "id": issue["key"],
                    "summary": issue["fields"]["summary"],
                    "status": issue["fields"]["status"]["name"],
                    "created": issue["fields"]["created"],
                    "updated": issue["fields"]["updated"]
                }
            )
            
            # Create person entity for the assignee if exists
            if issue["fields"].get("assignee"):
                assignee = issue["fields"]["assignee"]
                assignee_uri = graph.create_entity(
                    "Person",
                    {
                        "id": assignee["accountId"],
                        "name": assignee["displayName"],
                        "email": assignee.get("emailAddress", "")
                    }
                )
                
                # Link issue to assignee
                graph.create_relationship(
                    issue_uri,
                    "assignedTo",
                    assignee_uri
                )
        
        # Store the graph in the ontology store
        self.__configuration.ontology_store.insert(
            self.__configuration.ontology_store_name,
            graph
        )
        
        return graph
```

## Using Pipelines

Pipelines can be used directly in application code:

```python
# Create the pipeline
config = JiraTicketPipelineConfiguration(
    jira_integration=jira_integration,
    ontology_store=ontology_store_service
)
pipeline = JiraTicketPipeline(config)

# Run the pipeline
results = pipeline.run(
    JiraTicketPipelineParameters(
        project_key="ABI",
        max_issues=50
    )
)
```

Or exposed as an API endpoint:

```python
@router.post("/pipelines/jira-tickets")
def run_jira_pipeline(parameters: JiraTicketPipelineParameters):
    # Create the pipeline (or retrieve from a factory)
    pipeline = get_pipeline("jira_ticket")
    
    # Run the pipeline and return results
    results = pipeline.run(parameters)
    return {
        "success": True,
        "triples_count": len(results),
        "graph": results.serialize(format="turtle")
    }
```

## Next Steps

- Learn how to [Develop Pipelines](../guides/developing-pipelines.md)
- Understand how [Workflows](workflows.md) orchestrate pipelines
- Explore the [Ontology](ontology.md) structure that pipelines populate 