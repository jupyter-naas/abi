# Workflows

## Overview

Workflows in ABI are specialized components designed to implement specific intents or business logic. They serve as the bridge between user or agent intentions and the actual execution of those intentions using ABI's capabilities. Workflows inherit from the `Expose` interface, which means they can be executed by LLM agents through tools or via REST API calls.

Workflows sit at the top layer of ABI's architecture, orchestrating integrations and pipelines to fulfill specific business needs:

```
┌─────────────────┐
│    Workflows    │ ← Business logic layer
├─────────────────┤
│    Pipelines    │ ← Data transformation layer
├─────────────────┤
│  Integrations   │ ← External service communication layer
└─────────────────┘
```

## Purpose and Benefits

Workflows serve several key purposes in the ABI ecosystem:

1. **Intent Implementation**: They map specific user or agent intents to executable code.

2. **Business Logic Encapsulation**: They encapsulate business logic that can be reused across different contexts.

3. **Composability**: They can be composed together by LLM agents to fulfill more complex intents.

4. **Multi-Interface Exposure**: They can be exposed as tools for LLM agents, as API endpoints, as scheduled jobs, or run directly as Python code.

5. **Deterministic Execution**: They provide deterministic results for specific intents, unlike potentially variable LLM responses.

## How Workflows Work

A workflow typically follows this process flow:

1. **Configuration**: The workflow is initialized with configuration parameters that specify how it should operate, including which integrations or services it should use.

2. **Execution**: The workflow is executed with specific parameters that define the runtime behavior.

3. **Processing**: The workflow processes the parameters, potentially using integrations to communicate with external services, pipelines to transform data, or directly querying the ontology.

4. **Result**: The workflow returns a result that fulfills the intended purpose.

### Key Characteristics

- **Intent-Focused**: Workflows are designed around specific intents rather than technologies.

- **Composable**: Workflows can be composed together to fulfill more complex intents.

- **Exposed**: Workflows are exposed as both tools for LLM agents and as API endpoints.

- **Configurable**: Workflows are configured with the resources they need to operate.

- **Parameterized**: Workflows accept parameters that define their runtime behavior.

## Workflow Architecture

Workflows in ABI implement the `Workflow` abstract class, which extends the `Expose` interface. This design allows workflows to be exposed as both tools for LLM agents and as API endpoints.

### Key Components

1. **WorkflowConfiguration**: A dataclass that holds configuration parameters for the workflow, such as which integrations to use.

2. **WorkflowParameters**: A Pydantic model that defines the runtime parameters for workflow execution.

3. **Workflow Class**: The main class that implements the workflow logic, including the `run()` method that executes the workflow.

### The Expose Interface

Workflows implement the `Expose` interface, which provides two key methods:

1. **`as_tools()`**: Returns a list of LangChain StructuredTools that can be used by an LLM agent.
2. **`as_api()`**: Registers API routes for the workflow's functionality on a FastAPI router.

This design allows workflows to be easily exposed as both tools for LLM agents and as API endpoints.

## Use Cases

### Intent Implementation

The primary use case for workflows is to implement specific intents. For example:

- A **GetCustomersBySubscriptionDuration** workflow might implement the intent of finding customers who have been subscribed for a specific duration.
- An **AddCreditsToCustomer** workflow might implement the intent of adding credits to a customer's account.
- A **SendEmailToCustomer** workflow might implement the intent of sending an email to a customer.

### Composable Workflows

Workflows can be composed together by LLM agents to fulfill more complex intents. For example:

1. An agent receives the intent: "Reward customers who have been subscribed for more than 2 years with 1000 credits and send them a thank-you email."
2. The agent breaks this down into three sub-intents:
   - Find customers subscribed for more than 2 years
   - Add 1000 credits to each customer
   - Send a thank-you email to each customer
3. The agent executes three workflows in sequence to fulfill these sub-intents.

### Deterministic Execution

For cases where deterministic execution is required, a workflow can be created that composes other workflows in a specific sequence. This ensures that the same intent always results in the same execution path, unlike potentially variable LLM agent decisions.

## Creating a New Workflow

To create a new workflow in ABI, follow these steps:

1. Create a new file in `src/custom/modules/<module_name>/workflows/YourWorkflowName.py` using the template below
2. Implement the necessary methods to fulfill the intended purpose
3. Add configuration parameters as needed
4. Implement the `as_tools()` and `as_api()` methods to expose the workflow

### Workflow Template

```python
from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.modules.common.integrations import YourIntegration, YourIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import Any

@dataclass
class YourWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for YourWorkflow.
    
    Attributes:
        integration_config (YourIntegrationConfiguration): Configuration for the integration
    """
    integration_config: YourIntegrationConfiguration

class YourWorkflowParameters(WorkflowParameters):
    """Parameters for YourWorkflow execution.
    
    Attributes:
        parameter_1 (str): Description of parameter_1
        parameter_2 (int): Description of parameter_2
    """
    parameter_1: str = Field(..., description="Description of parameter_1")
    parameter_2: int = Field(..., description="Description of parameter_2")

class YourWorkflow(Workflow):
    __configuration: YourWorkflowConfiguration
    
    def __init__(self, configuration: YourWorkflowConfiguration):
        self.__configuration = configuration
        self.__integration = YourIntegration(self.__configuration.integration_config)

    def run(self, parameters: YourWorkflowParameters) -> Any:
        # Add your workflow logic here
        return "Your result"

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="your_workflow_name",
            description="Description of what your workflow does",
            func=lambda **kwargs: self.run(YourWorkflowParameters(**kwargs)),
            args_schema=YourWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/your_endpoint")
        def run_workflow(parameters: YourWorkflowParameters):
            return self.run(parameters)
```

## Workflow Implementation Guidelines

When implementing a workflow, follow these guidelines:

1. **Focus on Intent**: Design workflows around specific intents rather than technologies.

2. **Keep It Simple**: Each workflow should implement a single, well-defined intent.

3. **Compose When Needed**: For complex operations, consider composing multiple workflows rather than creating a monolithic workflow.

4. **Handle Errors Gracefully**: Implement proper error handling to ensure that the workflow can recover from failures.

5. **Document Thoroughly**: Document the workflow's purpose, configuration parameters, and runtime parameters thoroughly.

6. **Test Comprehensively**: Create tests to verify that the workflow correctly fulfills its intended purpose.

## Best Practices

When creating workflows, follow these best practices:

1. **Intent Mapping**: Clearly define the intent that the workflow implements and ensure that the implementation fulfills that intent.

2. **Granularity**: Keep workflows focused on specific intents to enable composition by LLM agents.

3. **Configuration Management**: Use the configuration class to manage dependencies and settings.

4. **Parameter Validation**: Validate runtime parameters to ensure they are valid before processing.

5. **Reusability**: Design workflows to be reusable across different contexts.

6. **Deterministic Execution**: Ensure that running the same workflow with the same parameters produces the same result.

7. **Composition**: Consider how workflows can be composed together to fulfill more complex intents.

## Examples

### Example 1: Customer Reward Workflow

Let's consider a scenario where we want to reward customers who have been subscribed for a certain duration:

1. **GetCustomersBySubscriptionDuration** workflow:
   - Intent: Find customers who have been subscribed for a specific duration
   - Parameters: `duration_years` (int)
   - Implementation: Queries the ontology to find customers who have been subscribed for the specified duration

2. **AddCreditsToCustomer** workflow:
   - Intent: Add credits to a customer's account
   - Parameters: `customer_id` (str), `credits` (int)
   - Implementation: Uses an integration to add credits to the customer's account in the service

3. **SendEmailToCustomer** workflow:
   - Intent: Send an email to a customer
   - Parameters: `customer_id` (str), `subject` (str), `body` (str)
   - Implementation: Uses an email integration to send an email to the customer

These three workflows can be composed together by an LLM agent to fulfill the more complex intent of rewarding long-term customers:

```
1. customers = GetCustomersBySubscriptionDuration(duration_years=2)
2. for customer in customers:
3.     AddCreditsToCustomer(customer_id=customer.id, credits=1000)
4.     SendEmailToCustomer(
5.         customer_id=customer.id,
6.         subject="Thank you for your loyalty!",
7.         body="As a token of our appreciation for being with us for 2+ years, we've added 1000 credits to your account."
8.     )
```

Alternatively, a deterministic workflow could be created that composes these three workflows:

```python
class RewardLongTermCustomersWorkflow(Workflow):
    def run(self, parameters: RewardLongTermCustomersParameters) -> Any:
        customers = self.__get_customers_workflow.run(GetCustomersBySubscriptionDurationParameters(
            duration_years=parameters.duration_years
        ))
        
        for customer in customers:
            self.__add_credits_workflow.run(AddCreditsToCustomerParameters(
                customer_id=customer.id,
                credits=parameters.credits
            ))
            
            self.__send_email_workflow.run(SendEmailToCustomerParameters(
                customer_id=customer.id,
                subject=parameters.email_subject,
                body=parameters.email_body
            ))
            
        return f"Rewarded {len(customers)} customers with {parameters.credits} credits."
```

## Conclusion

Workflows are a critical component of ABI's architecture, serving as the bridge between user or agent intentions and the actual execution of those intentions. By designing workflows around specific intents and making them composable, ABI enables both deterministic execution of business logic and flexible composition by LLM agents to fulfill complex intents.

Whether used directly by users through API calls, composed by LLM agents, or scheduled as background jobs, workflows provide a consistent way to package functionality that needs to be accessible through multiple interfaces. By following the guidelines and best practices outlined in this document, you can create effective workflows that enable ABI to fulfill a wide range of business needs.
