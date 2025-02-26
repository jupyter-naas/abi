# Workflows

This document explains the concept of Workflows in the ABI framework, their purpose, implementation, and how they orchestrate business processes using integrations and pipelines.

## What are Workflows?

Workflows are high-level components that orchestrate business processes by combining multiple operations, including calls to integrations, pipelines, and other services. They implement business logic and can be triggered by events, schedules, or direct invocation.

## Key Features

- **Process Orchestration**: Coordinate complex sequences of operations
- **Business Logic Implementation**: Encode business rules and decision-making
- **Integration Coordination**: Manage communication between multiple integrations
- **Pipeline Execution**: Trigger and monitor data processing pipelines
- **Error Handling**: Provide robust error handling and recovery mechanisms
- **Tool Registration**: Expose functionality as tools for assistants
- **API Exposure**: Make workflows available via RESTful APIs

## Workflow Architecture

```
┌───────────────────────────────────────────────────────────┐
│                       Workflow                            │
│                                                           │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────┐  │
│  │  Trigger      │    │  Process      │    │  Response │  │
│  │  Handler      │───►│  Executor     │───►│  Formatter│  │
│  │               │    │               │    │           │  │
│  └───────────────┘    └───────────────┘    └───────────┘  │
│                              │                  ▲         │
│                              ▼                  │         │
│                       ┌───────────────┐         │         │
│                       │  Integration/ │         │         │
│                       │  Pipeline     │─────────┘         │
│                       │  Coordinator  │                   │
│                       └───────────────┘                   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Workflow Components

### Configuration

Defines the workflow's behavior and dependencies:

```python
@dataclass
class SalesReportWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for the Sales Report Workflow.
    
    Attributes:
        salesforce_integration_config (SalesforceIntegrationConfiguration): Config for Salesforce
        ontology_store_service (IOntologyStoreService): The ontology store service
        report_template_path (str): Path to the report template
    """
    salesforce_integration_config: SalesforceIntegrationConfiguration
    ontology_store_service: IOntologyStoreService
    report_template_path: str
```

### Parameters

Runtime parameters that control the workflow's execution:

```python
class SalesReportWorkflowParameters(WorkflowParameters):
    """Parameters for the Sales Report Workflow.
    
    Attributes:
        region (str): Sales region to report on
        period (str): Time period ('monthly', 'quarterly', 'yearly')
        include_charts (bool): Whether to include charts in the report
    """
    region: str = Field(..., description="Sales region (e.g., 'North America', 'EMEA')")
    period: str = Field(..., description="Time period ('monthly', 'quarterly', 'yearly')")
    include_charts: bool = Field(True, description="Whether to include charts in the report")
```

### Process Logic

The main logic that orchestrates the business process:

```python
def run(self, parameters: SalesReportWorkflowParameters) -> Any:
    """Run the Sales Report Workflow.
    
    Args:
        parameters: Workflow parameters
        
    Returns:
        The generated sales report
    """
    # Initialize integrations
    salesforce = SalesforceIntegration(self.__configuration.salesforce_integration_config)
    
    # Determine date range based on period
    start_date, end_date = self._calculate_date_range(parameters.period)
    
    # Extract sales data via pipeline
    pipeline_config = SalesDataPipelineConfiguration(
        salesforce_integration=salesforce,
        ontology_store=self.__configuration.ontology_store_service,
        ontology_store_name="sales_data"
    )
    pipeline = SalesDataPipeline(pipeline_config)
    
    # Run pipeline to extract and transform data
    pipeline_result = pipeline.run(SalesDataPipelineParameters(
        start_date=start_date,
        end_date=end_date,
        include_opportunities=True
    ))
    
    # Query ontology to generate report data
    report_data = self._query_sales_data(parameters.region)
    
    # Generate the report
    report = self._generate_report(
        report_data, 
        parameters.region, 
        parameters.period, 
        parameters.include_charts
    )
    
    return report
```

### Helper Methods

Methods that help implement specific parts of the workflow:

```python
def _calculate_date_range(self, period: str) -> Tuple[str, str]:
    """Calculate start and end dates based on the period.
    
    Args:
        period: Time period ('monthly', 'quarterly', 'yearly')
        
    Returns:
        Tuple of start_date, end_date in ISO format
    """
    today = datetime.now()
    
    if period == "monthly":
        start_date = datetime(today.year, today.month, 1)
        if today.month == 12:
            end_date = datetime(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(today.year, today.month + 1, 1) - timedelta(days=1)
    elif period == "quarterly":
        quarter = (today.month - 1) // 3 + 1
        start_date = datetime(today.year, (quarter - 1) * 3 + 1, 1)
        if quarter == 4:
            end_date = datetime(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(today.year, quarter * 3 + 1, 1) - timedelta(days=1)
    else:  # yearly
        start_date = datetime(today.year, 1, 1)
        end_date = datetime(today.year, 12, 31)
    
    return start_date.isoformat(), end_date.isoformat()

def _query_sales_data(self, region: str) -> Dict:
    """Query the ontology store for sales data in the specified region.
    
    Args:
        region: The sales region to query
        
    Returns:
        Dictionary with processed sales data
    """
    sparql_query = f"""
        SELECT ?company ?revenue ?product ?date
        WHERE {{
            ?sale a :Sale ;
                  :hasCompany ?companyUri ;
                  :hasRegion "{region}" ;
                  :hasRevenue ?revenue ;
                  :hasProduct ?productUri ;
                  :hasDate ?date .
            ?companyUri :name ?company .
            ?productUri :name ?product .
        }}
    """
    
    results = self.__configuration.ontology_store_service.query(
        "sales_data", 
        sparql_query
    )
    
    # Process and aggregate results
    processed_data = {
        "total_revenue": 0,
        "by_company": {},
        "by_product": {},
        "by_date": {}
    }
    
    for result in results:
        company = result["company"]
        revenue = float(result["revenue"])
        product = result["product"]
        date = result["date"].split("T")[0]  # Just keep the date part
        
        processed_data["total_revenue"] += revenue
        
        # Aggregate by company
        if company not in processed_data["by_company"]:
            processed_data["by_company"][company] = 0
        processed_data["by_company"][company] += revenue
        
        # Aggregate by product
        if product not in processed_data["by_product"]:
            processed_data["by_product"][product] = 0
        processed_data["by_product"][product] += revenue
        
        # Aggregate by date
        if date not in processed_data["by_date"]:
            processed_data["by_date"][date] = 0
        processed_data["by_date"][date] += revenue
    
    return processed_data
```

## Creating a Workflow

A simplified example of creating a custom workflow:

```python
from abi.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from src.integrations import JiraIntegration, JiraIntegrationConfiguration
from src.pipelines import JiraTicketPipeline, JiraTicketPipelineConfiguration
from typing import Dict, List
from pydantic import BaseModel, Field
from dataclasses import dataclass

@dataclass
class TicketAnalysisWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for Ticket Analysis Workflow.
    
    Attributes:
        jira_integration_config (JiraIntegrationConfiguration): Config for Jira
        ontology_store_service (IOntologyStoreService): The ontology store service
    """
    jira_integration_config: JiraIntegrationConfiguration
    ontology_store_service: IOntologyStoreService

class TicketAnalysisWorkflowParameters(WorkflowParameters):
    """Parameters for Ticket Analysis Workflow.
    
    Attributes:
        project_key (str): Jira project key to analyze
        time_period_days (int): Number of days to analyze
        group_by (str): How to group results (assignee, status, priority)
    """
    project_key: str = Field(..., description="Jira project key (e.g., 'ABI')")
    time_period_days: int = Field(30, description="Time period in days to analyze")
    group_by: str = Field("assignee", description="How to group results (assignee, status, priority)")

class TicketAnalysisWorkflow(Workflow):
    """Workflow for analyzing Jira tickets and producing reports."""
    
    __configuration: TicketAnalysisWorkflowConfiguration
    
    def __init__(self, configuration: TicketAnalysisWorkflowConfiguration):
        self.__configuration = configuration
        # Initialize the Jira integration
        self.__jira = JiraIntegration(configuration.jira_integration_config)
    
    def run(self, parameters: TicketAnalysisWorkflowParameters) -> Dict:
        """Run the Ticket Analysis Workflow.
        
        Args:
            parameters: Workflow parameters
            
        Returns:
            Dictionary with analysis results
        """
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=parameters.time_period_days)
        
        # Set up and run the pipeline to extract ticket data
        pipeline_config = JiraTicketPipelineConfiguration(
            jira_integration=self.__jira,
            ontology_store=self.__configuration.ontology_store_service,
            ontology_store_name="jira_data"
        )
        pipeline = JiraTicketPipeline(pipeline_config)
        
        # Run the pipeline to populate the ontology
        pipeline.run(
            JiraTicketPipelineParameters(
                project_key=parameters.project_key,
                max_issues=1000  # Reasonable limit
            )
        )
        
        # Query the ontology store to get analysis data
        analysis_data = self._query_ticket_data(
            parameters.project_key,
            start_date.isoformat(),
            end_date.isoformat(),
            parameters.group_by
        )
        
        # Generate statistics and insights
        insights = self._generate_insights(analysis_data, parameters.group_by)
        
        # Return the combined results
        return {
            "project": parameters.project_key,
            "period": f"{start_date.date()} to {end_date.date()}",
            "analysis": analysis_data,
            "insights": insights
        }
```

## Exposing Workflows

Workflows can be exposed to assistants as tools:

```python
def as_tools(self) -> list[StructuredTool]:
    """Returns a list of LangChain tools for this workflow.
    
    Returns:
        list[StructuredTool]: List containing the workflow tool
    """
    return [StructuredTool(
        name="analyze_jira_tickets",
        description="Analyzes Jira tickets and produces statistical reports",
        func=lambda **kwargs: self.run(TicketAnalysisWorkflowParameters(**kwargs)),
        args_schema=TicketAnalysisWorkflowParameters
    )]
```

And as API endpoints:

```python
def as_api(self, router: APIRouter) -> None:
    """Adds API endpoints for this workflow to the given router.
    
    Args:
        router (APIRouter): FastAPI router to add endpoints to
    """
    @router.post("/workflows/ticket-analysis")
    def run_ticket_analysis(parameters: TicketAnalysisWorkflowParameters):
        return self.run(parameters)
```

## Next Steps

- Learn how to [Write Workflows](../guides/writing-workflows.md)
- Understand the [Assistants](assistants.md) that can use workflows as tools
- Explore how [Pipelines](pipelines.md) are used within workflows 