# Writing Workflows

This guide walks you through the process of creating workflows in the ABI framework to orchestrate complex business processes using pipelines, integrations, and other components.

## Prerequisites

Before writing a workflow, you should have:

- A working ABI installation
- Understanding of the [ABI architecture](../concepts/architecture.md)
- Familiarity with the [workflow concept](../concepts/workflows.md)
- Knowledge of [pipelines](../concepts/pipelines.md) and [integrations](../concepts/integrations.md)
- Experience with Python and asynchronous programming

## Workflow Structure

A typical ABI workflow consists of these components:

1. **Configuration Class**: Defines the workflow dependencies and settings
2. **Parameters Class**: Defines runtime parameters for workflow execution
3. **Workflow Class**: Implements the business logic using pipelines and integrations
4. **Tool Interface**: Exposes the workflow as tools for assistants
5. **API Interface**: Exposes the workflow via API endpoints

## Steps to Write a Workflow

### 1. Define the Workflow Configuration

Create a configuration class that extends `WorkflowConfiguration`:

```python
from abi.workflow import Workflow, WorkflowConfiguration
from dataclasses import dataclass
from src.integrations import EmailIntegration, EmailIntegrationConfiguration
from src.data.pipelines import CustomerDataPipeline, CustomerDataPipelineConfiguration
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

@dataclass
class CustomerFeedbackWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for Customer Feedback Workflow.
    
    Attributes:
        email_integration_config (EmailIntegrationConfiguration): Configuration for email integration
        customer_pipeline_config (CustomerDataPipelineConfiguration): Configuration for customer data pipeline
        ontology_store (IOntologyStoreService): The ontology store service
        max_parallel_requests (int): Maximum number of parallel requests to process
    """
    email_integration_config: EmailIntegrationConfiguration
    customer_pipeline_config: CustomerDataPipelineConfiguration
    ontology_store: IOntologyStoreService
    max_parallel_requests: int = 5
```

### 2. Define the Workflow Parameters

Create a parameters class that extends `WorkflowParameters`:

```python
from abi.workflow.workflow import WorkflowParameters
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CustomerFeedbackWorkflowParameters(WorkflowParameters):
    """Parameters for Customer Feedback Workflow execution.
    
    Attributes:
        feedback_id (str): Unique identifier for the feedback
        customer_id (str): ID of the customer providing feedback
        subject (str): Email subject or feedback topic
        feedback_text (str): The actual feedback text
        sentiment (Optional[str]): Pre-analyzed sentiment (positive, negative, neutral)
        categories (List[str]): Feedback categories or tags
        send_response (bool): Whether to send an automated response
    """
    feedback_id: str = Field(..., description="Unique identifier for the feedback")
    customer_id: str = Field(..., description="ID of the customer providing feedback")
    subject: str = Field(..., description="Email subject or feedback topic")
    feedback_text: str = Field(..., description="The actual feedback text")
    sentiment: Optional[str] = Field(None, description="Pre-analyzed sentiment (positive, negative, neutral)")
    categories: List[str] = Field(default_factory=list, description="Feedback categories or tags")
    send_response: bool = Field(True, description="Whether to send an automated response")
```

### 3. Implement the Workflow Class

Create the main workflow class that extends the `Workflow` base class:

```python
from abi import logger
from typing import Dict, Any
import asyncio
from abi.utils.Graph import ABIGraph
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS

class CustomerFeedbackWorkflow(Workflow):
    """Workflow for processing and responding to customer feedback."""
    
    __configuration: CustomerFeedbackWorkflowConfiguration
    __email_integration: EmailIntegration
    __customer_pipeline: CustomerDataPipeline
    
    def __init__(self, configuration: CustomerFeedbackWorkflowConfiguration):
        """Initialize the workflow with configuration.
        
        Args:
            configuration: The workflow configuration
        """
        self.__configuration = configuration
        
        # Initialize integrations and pipelines
        self.__email_integration = EmailIntegration(configuration.email_integration_config)
        self.__customer_pipeline = CustomerDataPipeline(configuration.customer_pipeline_config)
        
        logger.info("CustomerFeedbackWorkflow initialized")
    
    async def run(self, parameters: CustomerFeedbackWorkflowParameters) -> Dict[str, Any]:
        """Run the workflow to process customer feedback.
        
        Args:
            parameters: Workflow parameters
            
        Returns:
            Dict containing workflow results
        """
        logger.info(f"Processing feedback {parameters.feedback_id} from customer {parameters.customer_id}")
        
        # Track each step for reporting
        workflow_results = {
            "feedback_id": parameters.feedback_id,
            "customer_id": parameters.customer_id,
            "steps_completed": [],
            "success": False
        }
        
        try:
            # Step 1: Get customer data from the ontology
            customer_data = await self.__get_customer_data(parameters.customer_id)
            workflow_results["steps_completed"].append("customer_data_retrieved")
            
            # Step 2: Analyze sentiment if not provided
            if not parameters.sentiment:
                parameters.sentiment = await self.__analyze_sentiment(parameters.feedback_text)
            workflow_results["steps_completed"].append("sentiment_analyzed")
            workflow_results["sentiment"] = parameters.sentiment
            
            # Step 3: Categorize feedback if categories not provided
            if not parameters.categories:
                parameters.categories = await self.__categorize_feedback(parameters.feedback_text)
            workflow_results["steps_completed"].append("feedback_categorized")
            workflow_results["categories"] = parameters.categories
            
            # Step 4: Store feedback in ontology
            feedback_uri = await self.__store_feedback(parameters, customer_data)
            workflow_results["steps_completed"].append("feedback_stored")
            workflow_results["feedback_uri"] = str(feedback_uri)
            
            # Step 5: Send response if requested
            if parameters.send_response:
                response_id = await self.__send_response(parameters, customer_data)
                workflow_results["steps_completed"].append("response_sent")
                workflow_results["response_id"] = response_id
            
            workflow_results["success"] = True
            
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}")
            workflow_results["error"] = str(e)
            
        return workflow_results
```

### 4. Implement Helper Methods

Add methods to handle specific tasks within the workflow:

```python
async def __get_customer_data(self, customer_id: str) -> Dict[str, Any]:
    """Retrieve customer data from the ontology.
    
    Args:
        customer_id: ID of the customer
        
    Returns:
        Dict containing customer data
    """
    logger.debug(f"Retrieving data for customer {customer_id}")
    
    # Query the ontology store for customer data
    query = f"""
        PREFIX abi: <http://example.org/abi#>
        SELECT ?name ?email ?segment ?lifetime_value WHERE {{
            ?customer a abi:Customer ;
                      abi:id "{customer_id}" ;
                      abi:name ?name ;
                      abi:email ?email .
            OPTIONAL {{ ?customer abi:segment ?segment }}
            OPTIONAL {{ ?customer abi:lifetimeValue ?lifetime_value }}
        }}
    """
    
    results = self.__configuration.ontology_store.query("customer_data", query)
    
    if not results or len(results) == 0:
        logger.warning(f"No customer found with ID {customer_id}")
        # If customer not found, trigger the pipeline to fetch and store customer data
        await self.__fetch_customer_data(customer_id)
        results = self.__configuration.ontology_store.query("customer_data", query)
        
    if not results or len(results) == 0:
        raise ValueError(f"Customer with ID {customer_id} not found")
        
    # Extract the first result
    result = results[0]
    
    # Convert to a more convenient format
    customer_data = {
        "id": customer_id,
        "name": str(result.get("name", "")),
        "email": str(result.get("email", "")),
        "segment": str(result.get("segment", "standard")),
        "lifetime_value": float(result.get("lifetime_value", 0))
    }
    
    return customer_data

async def __fetch_customer_data(self, customer_id: str) -> None:
    """Fetch customer data using the customer data pipeline.
    
    Args:
        customer_id: ID of the customer
    """
    logger.info(f"Fetching data for customer {customer_id} via pipeline")
    
    # Create pipeline parameters
    from src.data.pipelines.customer_data import CustomerDataPipelineParameters
    params = CustomerDataPipelineParameters(
        customer_id=customer_id,
        include_transactions=False,
        include_interactions=True
    )
    
    # Run the pipeline to fetch and store customer data
    await self.__customer_pipeline.run_async(params)

async def __analyze_sentiment(self, text: str) -> str:
    """Analyze the sentiment of feedback text.
    
    Args:
        text: The feedback text to analyze
        
    Returns:
        str: Sentiment label (positive, negative, neutral)
    """
    logger.debug("Analyzing sentiment of feedback")
    
    # This would typically call an NLP service or model
    # Simplified example:
    positive_words = ["great", "excellent", "good", "love", "best", "amazing"]
    negative_words = ["bad", "terrible", "poor", "awful", "worst", "horrible"]
    
    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        return "positive"
    elif negative_count > positive_count:
        return "negative"
    else:
        return "neutral"

async def __categorize_feedback(self, text: str) -> List[str]:
    """Categorize feedback text into predefined categories.
    
    Args:
        text: The feedback text to categorize
        
    Returns:
        List[str]: List of category labels
    """
    logger.debug("Categorizing feedback")
    
    # This would typically call an NLP service or model
    # Simplified example:
    categories = []
    text_lower = text.lower()
    
    category_keywords = {
        "product": ["product", "feature", "functionality", "design"],
        "service": ["service", "support", "help", "assistance"],
        "pricing": ["price", "cost", "expensive", "cheap", "affordable"],
        "usability": ["usability", "user-friendly", "interface", "difficult", "easy"],
        "performance": ["performance", "speed", "slow", "fast", "crash"]
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            categories.append(category)
    
    if not categories:
        categories.append("general")
        
    return categories

async def __store_feedback(
    self, 
    parameters: CustomerFeedbackWorkflowParameters, 
    customer_data: Dict[str, Any]
) -> URIRef:
    """Store feedback in the ontology.
    
    Args:
        parameters: Workflow parameters
        customer_data: Customer data
        
    Returns:
        URIRef: URI of the created feedback entity
    """
    logger.info(f"Storing feedback {parameters.feedback_id} in ontology")
    
    # Create a new graph for this feedback
    graph = ABIGraph()
    
    # Create the feedback entity
    feedback_uri = graph.create_entity(
        "Feedback",
        {
            "id": parameters.feedback_id,
            "subject": parameters.subject,
            "text": parameters.feedback_text,
            "sentiment": parameters.sentiment,
            "timestamp": datetime.now().isoformat()
        }
    )
    
    # Add categories
    for category in parameters.categories:
        graph.add_property(feedback_uri, "hasCategory", category)
    
    # Get or create customer entity
    customer_uri = graph.create_entity(
        "Customer",
        {
            "id": customer_data["id"],
            "name": customer_data["name"],
            "email": customer_data["email"],
            "segment": customer_data["segment"]
        }
    )
    
    # Link feedback to customer
    graph.create_relationship(
        feedback_uri,
        "providedBy",
        customer_uri
    )
    
    # Store the graph in the ontology store
    self.__configuration.ontology_store.insert(
        "feedback_data",
        graph
    )
    
    return feedback_uri

async def __send_response(
    self, 
    parameters: CustomerFeedbackWorkflowParameters, 
    customer_data: Dict[str, Any]
) -> str:
    """Send an automated response to the customer.
    
    Args:
        parameters: Workflow parameters
        customer_data: Customer data
        
    Returns:
        str: Response message ID
    """
    logger.info(f"Sending response to customer {parameters.customer_id}")
    
    # Generate response based on sentiment and categories
    subject = f"RE: {parameters.subject}"
    
    # Template selection based on sentiment
    if parameters.sentiment == "positive":
        template = "positive_feedback_response.html"
    elif parameters.sentiment == "negative":
        template = "negative_feedback_response.html"
    else:
        template = "neutral_feedback_response.html"
    
    # Template data
    template_data = {
        "customer_name": customer_data["name"],
        "feedback_id": parameters.feedback_id,
        "categories": parameters.categories,
        "is_priority": customer_data["segment"] in ["premium", "enterprise"]
    }
    
    # Send email using integration
    message_id = await self.__email_integration.send_templated_email(
        recipient=customer_data["email"],
        subject=subject,
        template=template,
        template_data=template_data
    )
    
    return message_id
```

### 5. Add Tool Interface

Implement methods to expose the workflow as langchain tools:

```python
from langchain_core.tools import StructuredTool
from typing import List

def as_tools(self) -> List[StructuredTool]:
    """Returns a list of LangChain tools for this workflow.
    
    Returns:
        List[StructuredTool]: List containing the workflow tools
    """
    return [
        StructuredTool(
            name="process_customer_feedback",
            description="Process customer feedback and optionally send a response",
            func=lambda **kwargs: asyncio.run(self.run(CustomerFeedbackWorkflowParameters(**kwargs))),
            args_schema=CustomerFeedbackWorkflowParameters
        ),
        StructuredTool(
            name="analyze_feedback_sentiment",
            description="Analyze the sentiment of customer feedback text",
            func=lambda text: asyncio.run(self.__analyze_sentiment(text)),
            args_schema=lambda: {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The feedback text to analyze"}
                },
                "required": ["text"]
            }
        ),
        StructuredTool(
            name="categorize_feedback_text",
            description="Categorize feedback text into predefined categories",
            func=lambda text: asyncio.run(self.__categorize_feedback(text)),
            args_schema=lambda: {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The feedback text to categorize"}
                },
                "required": ["text"]
            }
        )
    ]
```

### 6. Add API Interface

Implement methods to expose the workflow via API:

```python
from fastapi import APIRouter, BackgroundTasks
from typing import List, Dict, Any

def as_api(self, router: APIRouter) -> None:
    """Adds API endpoints for this workflow to the given router.
    
    Args:
        router (APIRouter): FastAPI router to add endpoints to
    """
    @router.post("/workflows/customer-feedback")
    async def process_feedback(
        parameters: CustomerFeedbackWorkflowParameters,
        background_tasks: BackgroundTasks
    ):
        """Process customer feedback."""
        # For quick response, run in background
        background_tasks.add_task(self.run, parameters)
        return {
            "status": "processing",
            "feedback_id": parameters.feedback_id,
            "customer_id": parameters.customer_id
        }
    
    @router.get("/workflows/customer-feedback/{feedback_id}")
    async def get_feedback_status(feedback_id: str):
        """Get status of feedback processing."""
        # Query the ontology for feedback status
        query = f"""
            PREFIX abi: <http://example.org/abi#>
            SELECT ?timestamp ?sentiment ?categories ?response_sent WHERE {{
                ?feedback a abi:Feedback ;
                          abi:id "{feedback_id}" ;
                          abi:timestamp ?timestamp ;
                          abi:sentiment ?sentiment .
                OPTIONAL {{ ?feedback abi:hasCategory ?categories }}
                OPTIONAL {{ ?feedback abi:responseSent ?response_sent }}
            }}
        """
        
        results = self.__configuration.ontology_store.query("feedback_data", query)
        
        if not results or len(results) == 0:
            return {"status": "not_found", "feedback_id": feedback_id}
            
        # Process results
        categories = [str(result["categories"]) for result in results if "categories" in result]
        response_sent = any(result.get("response_sent") == Literal(True) for result in results)
        
        return {
            "status": "processed",
            "feedback_id": feedback_id,
            "timestamp": str(results[0]["timestamp"]),
            "sentiment": str(results[0]["sentiment"]),
            "categories": categories,
            "response_sent": response_sent
        }
```

## Testing Your Workflow

### 1. Unit Testing

Create unit tests for your workflow:

```python
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

class TestCustomerFeedbackWorkflow(unittest.TestCase):
    """Tests for the Customer Feedback Workflow."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mocks
        self.email_integration_config = MagicMock()
        self.customer_pipeline_config = MagicMock()
        self.ontology_store = MagicMock()
        
        # Configure mocks
        self.ontology_store.query = MagicMock(return_value=[{
            "name": "Test Customer",
            "email": "test@example.com",
            "segment": "standard",
            "lifetime_value": 1000.0
        }])
        
        # Create configuration
        self.config = CustomerFeedbackWorkflowConfiguration(
            email_integration_config=self.email_integration_config,
            customer_pipeline_config=self.customer_pipeline_config,
            ontology_store=self.ontology_store
        )
        
        # Create workflow with mocked dependencies
        with patch('src.integrations.EmailIntegration') as MockEmailIntegration, \
             patch('src.data.pipelines.CustomerDataPipeline') as MockCustomerPipeline:
            
            self.mock_email_integration = MockEmailIntegration.return_value
            self.mock_email_integration.send_templated_email = AsyncMock(return_value="message-123")
            
            self.mock_customer_pipeline = MockCustomerPipeline.return_value
            self.mock_customer_pipeline.run_async = AsyncMock()
            
            self.workflow = CustomerFeedbackWorkflow(self.config)
    
    def test_analyze_sentiment(self):
        """Test sentiment analysis."""
        sentiment = asyncio.run(self.workflow._CustomerFeedbackWorkflow__analyze_sentiment(
            "This product is great and I love it!"
        ))
        self.assertEqual(sentiment, "positive")
        
        sentiment = asyncio.run(self.workflow._CustomerFeedbackWorkflow__analyze_sentiment(
            "This product is terrible and I hate it!"
        ))
        self.assertEqual(sentiment, "negative")
        
        sentiment = asyncio.run(self.workflow._CustomerFeedbackWorkflow__analyze_sentiment(
            "This product is okay."
        ))
        self.assertEqual(sentiment, "neutral")
    
    def test_categorize_feedback(self):
        """Test feedback categorization."""
        categories = asyncio.run(self.workflow._CustomerFeedbackWorkflow__categorize_feedback(
            "The product design is excellent but the price is too high."
        ))
        self.assertIn("product", categories)
        self.assertIn("pricing", categories)
    
    def test_run_workflow(self):
        """Test running the full workflow."""
        # Mock ontology store insert
        self.ontology_store.insert = MagicMock()
        
        # Create test parameters
        params = CustomerFeedbackWorkflowParameters(
            feedback_id="feedback-123",
            customer_id="customer-456",
            subject="Product Feedback",
            feedback_text="The product is great!",
            send_response=True
        )
        
        # Run workflow
        results = asyncio.run(self.workflow.run(params))
        
        # Verify results
        self.assertTrue(results["success"])
        self.assertEqual(results["feedback_id"], "feedback-123")
        self.assertEqual(results["customer_id"], "customer-456")
        self.assertIn("sentiment_analyzed", results["steps_completed"])
        self.assertIn("feedback_categorized", results["steps_completed"])
        self.assertIn("feedback_stored", results["steps_completed"])
        self.assertIn("response_sent", results["steps_completed"])
        self.assertEqual(results["sentiment"], "positive")
        self.assertEqual(results["response_id"], "message-123")
```

### 2. Integration Testing

```python
from abi.testing import IntegrationTestCase
from src import config

class TestCustomerFeedbackWorkflowIntegration(IntegrationTestCase):
    """Integration tests for the Customer Feedback Workflow."""
    
    async def asyncSetUp(self):
        """Set up the test environment."""
        # Get real dependencies from config
        self.email_integration_config = config.get_email_integration_config()
        self.customer_pipeline_config = config.get_customer_pipeline_config()
        self.ontology_store = config.get_ontology_store_service()
        
        # Create test customer in the ontology
        self.test_customer_id = "test-customer-" + str(int(time.time()))
        await self.create_test_customer(self.test_customer_id)
        
        # Create workflow configuration
        self.config = CustomerFeedbackWorkflowConfiguration(
            email_integration_config=self.email_integration_config,
            customer_pipeline_config=self.customer_pipeline_config,
            ontology_store=self.ontology_store
        )
        
        # Create workflow
        self.workflow = CustomerFeedbackWorkflow(self.config)
    
    async def create_test_customer(self, customer_id):
        """Create a test customer in the ontology."""
        graph = ABIGraph()
        
        customer_uri = graph.create_entity(
            "Customer",
            {
                "id": customer_id,
                "name": "Integration Test Customer",
                "email": "test@example.com",
                "segment": "standard"
            }
        )
        
        self.ontology_store.insert("customer_data", graph)
    
    async def test_workflow_end_to_end(self):
        """Test the workflow end-to-end."""
        # Create test parameters
        feedback_id = "feedback-" + str(int(time.time()))
        params = CustomerFeedbackWorkflowParameters(
            feedback_id=feedback_id,
            customer_id=self.test_customer_id,
            subject="Integration Test Feedback",
            feedback_text="This is a test of the workflow integration. The product is great!",
            send_response=True
        )
        
        # Run workflow
        results = await self.workflow.run(params)
        
        # Verify results
        self.assertTrue(results["success"])
        self.assertEqual(results["feedback_id"], feedback_id)
        self.assertEqual(results["customer_id"], self.test_customer_id)
        self.assertEqual(results["sentiment"], "positive")
        
        # Verify data in ontology
        query = f"""
            PREFIX abi: <http://example.org/abi#>
            ASK {{
                ?feedback a abi:Feedback ;
                          abi:id "{feedback_id}" .
            }}
        """
        
        result = self.ontology_store.query("feedback_data", query)
        self.assertTrue(result)
    
    async def asyncTearDown(self):
        """Clean up after tests."""
        # Remove test data
        query = f"""
            PREFIX abi: <http://example.org/abi#>
            DELETE {{
                ?customer ?p ?o .
                ?feedback ?p2 ?o2 .
            }}
            WHERE {{
                ?customer a abi:Customer ;
                          abi:id "{self.test_customer_id}" ;
                          ?p ?o .
                OPTIONAL {{
                    ?feedback a abi:Feedback ;
                              abi:providedBy ?customer ;
                              ?p2 ?o2 .
                }}
            }}
        """
        
        self.ontology_store.update("customer_data", query)
        self.ontology_store.update("feedback_data", query)
```

## Best Practices

### Error Handling

Implement robust error handling within workflows:

```python
async def run_with_error_handling(self, parameters: CustomerFeedbackWorkflowParameters) -> Dict[str, Any]:
    """Run workflow with error handling.
    
    Args:
        parameters: Workflow parameters
        
    Returns:
        Dict containing workflow results
    """
    try:
        return await self.run(parameters)
    except ValueError as e:
        logger.error(f"Validation error in workflow: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "validation_error"
        }
    except IOError as e:
        logger.error(f"I/O error in workflow: {str(e)}")
        return {
            "success": False, 
            "error": str(e),
            "error_type": "io_error",
            "retriable": True
        }
    except Exception as e:
        logger.error(f"Unexpected error in workflow: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error"
        }
```

### Performance Optimization

Use asynchronous patterns for efficient execution:

```python
async def __process_batch(self, customer_ids: List[str]) -> List[Dict[str, Any]]:
    """Process a batch of customers in parallel.
    
    Args:
        customer_ids: List of customer IDs to process
        
    Returns:
        List of results, one per customer
    """
    # Create tasks for all customers
    tasks = []
    for customer_id in customer_ids:
        params = CustomerFeedbackWorkflowParameters(
            feedback_id=f"batch-{int(time.time())}-{customer_id}",
            customer_id=customer_id,
            subject="Batch Processing",
            feedback_text="Auto-generated feedback for batch processing",
            send_response=False
        )
        tasks.append(self.run(params))
    
    # Run all tasks concurrently with limitation
    semaphore = asyncio.Semaphore(self.__configuration.max_parallel_requests)
    
    async def run_with_semaphore(task):
        async with semaphore:
            return await task
    
    limited_tasks = [run_with_semaphore(task) for task in tasks]
    results = await asyncio.gather(*limited_tasks, return_exceptions=True)
    
    # Process results
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "customer_id": customer_ids[i],
                "success": False,
                "error": str(result)
            })
        else:
            processed_results.append(result)
    
    return processed_results
```

### Stateful Workflows

Implement state management for long-running workflows:

```python
async def start_workflow(self, parameters: CustomerFeedbackWorkflowParameters) -> str:
    """Start a workflow and return a workflow ID.
    
    Args:
        parameters: Workflow parameters
        
    Returns:
        str: Workflow ID for tracking status
    """
    workflow_id = f"workflow-{uuid.uuid4()}"
    
    # Store initial state
    state = {
        "workflow_id": workflow_id,
        "parameters": parameters.dict(),
        "status": "started",
        "start_time": datetime.now().isoformat(),
        "current_step": "initialize",
        "steps_completed": []
    }
    
    await self.__store_workflow_state(workflow_id, state)
    
    # Start workflow in background
    asyncio.create_task(self.__run_with_state_tracking(workflow_id, parameters))
    
    return workflow_id

async def __run_with_state_tracking(self, workflow_id: str, parameters: CustomerFeedbackWorkflowParameters) -> None:
    """Run workflow with state tracking.
    
    Args:
        workflow_id: Workflow ID
        parameters: Workflow parameters
    """
    try:
        # Update state to processing
        await self.__update_workflow_state(workflow_id, {"status": "processing"})
        
        # Run each step with state updates
        
        # Step 1: Get customer data
        await self.__update_workflow_state(workflow_id, {"current_step": "get_customer_data"})
        customer_data = await self.__get_customer_data(parameters.customer_id)
        await self.__update_workflow_state(workflow_id, {
            "steps_completed": ["get_customer_data"],
            "customer_data": customer_data
        })
        
        # Step 2: Analyze sentiment
        await self.__update_workflow_state(workflow_id, {"current_step": "analyze_sentiment"})
        if not parameters.sentiment:
            parameters.sentiment = await self.__analyze_sentiment(parameters.feedback_text)
        await self.__update_workflow_state(workflow_id, {
            "steps_completed": ["get_customer_data", "analyze_sentiment"],
            "sentiment": parameters.sentiment
        })
        
        # ... Continue with other steps ...
        
        # Finalize workflow
        await self.__update_workflow_state(workflow_id, {
            "status": "completed",
            "end_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in workflow {workflow_id}: {str(e)}")
        await self.__update_workflow_state(workflow_id, {
            "status": "failed",
            "error": str(e),
            "end_time": datetime.now().isoformat()
        })

async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
    """Get workflow status by ID.
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        Dict containing workflow state
    """
    # Retrieve state from storage
    state = await self.__get_workflow_state(workflow_id)
    
    if not state:
        return {"status": "not_found", "workflow_id": workflow_id}
        
    return state
```

## Advanced Workflow Features

### Branching Logic

Implement conditional workflows with different paths:

```python
async def __determine_response_action(self, parameters: CustomerFeedbackWorkflowParameters, customer_data: Dict[str, Any]) -> str:
    """Determine the appropriate response action based on feedback and customer data.
    
    Args:
        parameters: Workflow parameters
        customer_data: Customer data
        
    Returns:
        str: Action to take (auto_respond, escalate, no_action)
    """
    # VIP customers always get personal attention
    if customer_data["segment"] in ["premium", "enterprise"]:
        return "escalate"
        
    # Negative feedback from high-value customers gets escalated
    if parameters.sentiment == "negative" and customer_data["lifetime_value"] > 5000:
        return "escalate"
        
    # Specific categories that need escalation
    critical_categories = ["bug", "security", "billing", "legal"]
    if any(category in critical_categories for category in parameters.categories):
        return "escalate"
        
    # Standard auto-response for most cases
    if parameters.send_response:
        return "auto_respond"
        
    # No action needed
    return "no_action"

async def __process_by_action(self, action: str, parameters: CustomerFeedbackWorkflowParameters, customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process feedback based on determined action.
    
    Args:
        action: Action to take
        parameters: Workflow parameters
        customer_data: Customer data
        
    Returns:
        Dict containing action results
    """
    results = {"action": action}
    
    if action == "auto_respond":
        message_id = await self.__send_response(parameters, customer_data)
        results["message_id"] = message_id
        
    elif action == "escalate":
        ticket_id = await self.__create_support_ticket(parameters, customer_data)
        results["ticket_id"] = ticket_id
        
        # Send acknowledgment email
        message_id = await self.__send_escalation_acknowledgment(parameters, customer_data)
        results["message_id"] = message_id
        
    # No action case just returns the action type
    
    return results
```

### Event-Driven Workflows

Implement event-driven patterns for workflow integration:

```python
async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle an external event in the workflow.
    
    Args:
        event_type: Type of event
        event_data: Event data
        
    Returns:
        Dict containing event handling results
    """
    if event_type == "new_feedback":
        # Create parameters from event data
        parameters = CustomerFeedbackWorkflowParameters(
            feedback_id=event_data["id"],
            customer_id=event_data["customer_id"],
            subject=event_data["subject"],
            feedback_text=event_data["text"],
            send_response=event_data.get("send_response", True)
        )
        
        # Process the feedback
        return await self.run(parameters)
        
    elif event_type == "feedback_response":
        # Update feedback with response information
        feedback_id = event_data["feedback_id"]
        response_text = event_data["response_text"]
        
        # Update the ontology
        graph = ABIGraph()
        
        # Find the feedback entity
        query = f"""
            PREFIX abi: <http://example.org/abi#>
            SELECT ?feedback WHERE {{
                ?feedback a abi:Feedback ;
                          abi:id "{feedback_id}" .
            }}
        """
        
        results = self.__configuration.ontology_store.query("feedback_data", query)
        
        if not results or len(results) == 0:
            return {"status": "error", "message": f"Feedback {feedback_id} not found"}
            
        feedback_uri = results[0]["feedback"]
        
        # Add response information
        graph.add_property(feedback_uri, "hasResponse", response_text)
        graph.add_property(feedback_uri, "responseTime", datetime.now().isoformat())
        
        # Store in ontology
        self.__configuration.ontology_store.insert("feedback_data", graph)
        
        return {
            "status": "success",
            "feedback_id": feedback_id,
            "action": "response_recorded"
        }
    
    else:
        return {
            "status": "error",
            "message": f"Unknown event type: {event_type}"
        }
```

## Next Steps

- Learn about [Managing Ontologies](managing-ontologies.md) to understand how your workflow data is stored
- Check out [Creating Assistants](creating-assistants.md) to build interfaces that use your workflows
- Explore [Developing Pipelines](developing-pipelines.md) to enhance the data processing capabilities of your workflows 