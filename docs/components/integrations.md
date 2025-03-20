# Integrations Architecture

Integrations in ABI are specialized classes that serve as technological bridges between ABI and third-party APIs, services, or technologies. They provide a standardized way to interact with external systems.

## Design Philosophy

Integrations are the most atomic components in ABI, designed to be:
1. **Self-contained**: Minimal dependencies on other ABI components
2. **Technology-specific**: Each integration focuses on a single external service
3. **Interface-consistent**: All integrations follow the same basic structure
4. **Authentication-aware**: Handle credentials and authentication flow

## Integration Structure

The architecture of an integration consists of two main components: the Integration Class and the Configuration Class.

1. **Integration Class**: This class serves as the primary interface for interacting with a specific external service. It encapsulates the logic required to communicate with the service, ensuring that all interactions are handled consistently and efficiently.

2. **Configuration Class**: This class is responsible for storing essential information needed to connect to the external service. It includes:
   - **API Keys**: These are the credentials required to authenticate requests to the external service.
   - **Endpoints**: These are the specific URLs that the integration will use to make API calls to the service.
   - **Connection Parameters**: This includes any additional settings or parameters necessary for establishing a connection to the service.

3. **Integration Methods**: Within the Integration Class, several methods are defined to facilitate various operations:
   - **API Request Handling**: This method constructs and sends requests to the external service, managing the communication process.
   - **Authentication**: This method handles the authentication process, ensuring that the integration can securely access the external service.
   - **Data Formatting**: This method prepares data for both sending to and receiving from the external service, ensuring that it is in the correct format.
   - **Error Handling**: This method manages any errors that may arise during API requests or data processing, providing a robust way to deal with issues.

Overall, this structure ensures that integrations are self-contained, technology-specific, and consistent in their interface, while also being aware of authentication requirements.

Integrations are organized into the following directories:

- `src/core/integrations/`: Core integrations
- `src/integrations/custom/`: Custom integrations


## Key Components

1. **Integration Configuration Class**:
   - Dataclass extending `IntegrationConfiguration`
   - Stores all required credentials and settings
   - Enables easy configuration management and dependency injection

2. **Integration Class**:
   - Extends the base `Integration` class
   - Implements methods to interact with external service
   - Handles authentication, API requests, and error management
   - May expose methods as tools for LLM agents

## Implementation Example


## Key Components

1. **Pipeline Configuration Class**:
   - Dataclass extending `PipelineConfiguration`
   - Contains necessary service references (integrations, ontology store)
   - Defines persistent configuration options

2. **Pipeline Parameters Class**:
   - Pydantic model extending `PipelineParameters`
   - Defines runtime parameters for pipeline execution
   - Used for input validation and documentation

3. **Pipeline Class**:
   - Extends the base `Pipeline` class
   - Implements the `run()` method for data transformation
   - May implement the `trigger()` method for event-based execution
   - Exposes itself as tools for LLM agents and/or API endpoints

