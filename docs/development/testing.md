# Testing Guidelines

This document provides guidelines and best practices for testing the ABI framework, covering unit testing, integration testing, and end-to-end testing approaches.

## Testing Philosophy

The ABI framework follows these testing principles:

1. **Test-Driven Development**: Write tests before implementing features when possible
2. **Comprehensive Coverage**: Aim for high test coverage across all components
3. **Realistic Testing**: Test with realistic data and scenarios
4. **Fast Feedback**: Tests should run quickly to provide immediate feedback
5. **Independence**: Tests should be independent and not rely on other tests

## Test Types

### Unit Tests

Unit tests verify individual components in isolation. They should be:

- Fast to execute
- Independent of external systems
- Focused on a single unit of functionality

### Integration Tests

Integration tests verify that components work together correctly. They:

- Test interactions between components
- May involve multiple classes or modules
- Can include database interactions or API calls (with appropriate mocking)

### End-to-End Tests

End-to-end tests verify entire workflows. They:

- Test complete user workflows
- Exercise the system as a whole
- May involve multiple subsystems

## Testing Technologies

The ABI framework uses these testing tools:

- **pytest**: Primary testing framework
- **unittest.mock**: For mocking dependencies
- **pytest-cov**: For test coverage reporting
- **responses**: For mocking HTTP responses
- **pytest-asyncio**: For testing asynchronous code

## Directory Structure

Tests are organized as follows:

```
abi/
├── src/
│   └── ...
└── tests/
    ├── unit/
    │   ├── assistants/
    │   ├── integrations/
    │   ├── pipelines/
    │   ├── workflows/
    │   └── ...
    ├── integration/
    │   ├── assistants/
    │   ├── integrations/
    │   ├── pipelines/
    │   ├── workflows/
    │   └── ...
    └── e2e/
        ├── scenarios/
        └── fixtures/
```

## Unit Testing Guidelines

### Test File Naming

Test files should be named with `test_` prefix followed by the name of the module they're testing:

- Module: `src/assistants/assistant.py`
- Test file: `tests/unit/assistants/test_assistant.py`

### Test Case Naming

Test functions should have descriptive names that indicate what they're testing:

```python
def test_assistant_responds_with_error_when_given_invalid_input():
    # Test implementation
```

### Test Structure

Follow the Arrange-Act-Assert (AAA) pattern:

```python
def test_calculate_average():
    # Arrange
    numbers = [1, 2, 3, 4, 5]
    
    # Act
    result = calculate_average(numbers)
    
    # Assert
    assert result == 3
```

### Mocking

Use mocks to isolate the unit under test:

```python
from unittest.mock import Mock, patch

@patch('src.integrations.github_integration.requests')
def test_github_integration_handles_rate_limit(mock_requests):
    # Arrange
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.json.return_value = {"message": "Rate limit exceeded"}
    mock_requests.get.return_value = mock_response
    
    integration = GithubIntegration(config)
    
    # Act & Assert
    with pytest.raises(RateLimitException):
        integration.get_repository("owner", "repo")
```

### Parameterized Tests

Use parameterized tests for testing multiple inputs:

```python
import pytest

@pytest.mark.parametrize("input_value, expected_output", [
    ([], ValueError),
    ([1], 1),
    ([1, 2, 3], 2),
    ([1, 2, 3, 4], 2.5),
])
def test_calculate_average_with_various_inputs(input_value, expected_output):
    if isinstance(expected_output, type) and issubclass(expected_output, Exception):
        with pytest.raises(expected_output):
            calculate_average(input_value)
    else:
        result = calculate_average(input_value)
        assert result == expected_output
```

### Testing Exceptions

Test both normal operation and error conditions:

```python
def test_division_by_zero_raises_error():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)
```

## Integration Testing Guidelines

### Setup and Teardown

Use fixtures for setup and teardown:

```python
@pytest.fixture
def db_connection():
    # Setup
    connection = create_test_db_connection()
    yield connection
    # Teardown
    connection.close()

def test_database_integration(db_connection):
    # Test using the connection
    result = db_connection.execute("SELECT 1")
    assert result == 1
```

### Test Doubles

Use appropriate test doubles for external dependencies:

- **Stub**: Simple implementation that returns predefined responses
- **Mock**: Records calls and can verify interactions
- **Fake**: Lightweight implementation of a component (e.g., in-memory database)
- **Spy**: Wrapper that records usage of the real component

### Testing API Integrations

Use `responses` to mock HTTP APIs:

```python
import responses

@responses.activate
def test_github_integration():
    # Setup mock responses
    responses.add(
        responses.GET,
        "https://api.github.com/repos/owner/repo",
        json={"name": "repo", "id": 12345},
        status=200
    )
    
    # Test the integration
    integration = GithubIntegration(config)
    repo = integration.get_repository("owner", "repo")
    
    assert repo["name"] == "repo"
    assert repo["id"] == 12345
```

### Testing Database Integrations

Use in-memory databases for testing:

```python
@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    
    yield session
    
    session.close()

def test_user_repository(in_memory_db):
    repo = UserRepository(in_memory_db)
    repo.add(User(name="Test User", email="test@example.com"))
    
    user = repo.get_by_email("test@example.com")
    assert user.name == "Test User"
```

## End-to-End Testing Guidelines

### Test Scenarios

Write scenarios in terms of user actions:

```python
def test_customer_support_workflow():
    # Setup customer and support context
    customer = create_test_customer()
    assistant = create_support_assistant()
    
    # User asks a question
    response = assistant.process_message(
        "I need help with my recent order #12345"
    )
    
    # Verify appropriate response
    assert "order #12345" in response
    assert "shipped on" in response
    # More assertions about the response content...
```

### Test Data

Use realistic test data:

- Create test fixtures for common entities
- Use factory methods to create test objects
- Consider using snapshot testing for complex responses

### Environmental Setup

Provide clear setup instructions for end-to-end tests:

```python
@pytest.fixture(scope="session")
def e2e_environment():
    """Set up environment for E2E tests.
    
    Requires:
    - Docker
    - Docker Compose
    
    Returns:
        dict: Environment configuration
    """
    # Start services with Docker Compose
    subprocess.run(["docker-compose", "up", "-d"])
    
    # Wait for services to be ready
    wait_for_services()
    
    # Configure test environment
    config = {
        "api_url": "http://localhost:8000",
        "auth_token": "test-token"
    }
    
    yield config
    
    # Cleanup
    subprocess.run(["docker-compose", "down"])
```

## Testing Specific Components

### Testing Assistants

```python
def test_assistant_with_tools():
    # Arrange
    mock_tool = Mock()
    mock_tool.execute.return_value = {"result": "success"}
    
    assistant = Assistant(
        name="Test Assistant",
        tools=[mock_tool]
    )
    
    # Act
    response = assistant.process_message("Use the tool")
    
    # Assert
    assert mock_tool.execute.called
    assert "success" in response
```

### Testing Integrations

```python
def test_integration_authentication():
    # Arrange
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"token": "test-token"}
    
    session = Mock()
    session.post.return_value = mock_response
    
    integration = SomeIntegration(config, session=session)
    
    # Act
    result = integration.authenticate()
    
    # Assert
    assert result == "test-token"
    session.post.assert_called_with(
        "https://api.example.com/auth",
        json={"username": "test", "password": "password"}
    )
```

### Testing Pipelines

```python
def test_pipeline_extracts_and_transforms_data():
    # Arrange
    mock_integration = Mock()
    mock_integration.get_data.return_value = [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"}
    ]
    
    mock_ontology_store = Mock()
    
    pipeline = DataPipeline(
        integration=mock_integration,
        ontology_store=mock_ontology_store
    )
    
    # Act
    result = pipeline.run(parameters)
    
    # Assert
    assert len(result) == 2
    mock_ontology_store.insert.assert_called_once()
    # Additional assertions about the transformed data
```

### Testing Workflows

```python
def test_workflow_orchestrates_components():
    # Arrange
    mock_pipeline = Mock()
    mock_assistant = Mock()
    
    workflow = CustomerSupportWorkflow(
        pipeline=mock_pipeline,
        assistant=mock_assistant
    )
    
    # Act
    result = workflow.run({"customer_id": "123"})
    
    # Assert
    mock_pipeline.run.assert_called_once()
    assert "status" in result
    # Additional assertions about the workflow results
```

### Testing Ontology

```python
def test_ontology_graph_creation():
    # Arrange
    graph = ABIGraph()
    
    # Act
    person_uri = graph.create_entity(
        "Person",
        {"name": "John Doe", "email": "john@example.com"}
    )
    
    org_uri = graph.create_entity(
        "Organization",
        {"name": "Acme Corp"}
    )
    
    graph.create_relationship(person_uri, "worksFor", org_uri)
    
    # Assert
    assert (person_uri, RDF.type, URIRef("http://example.org/Person")) in graph
    assert (person_uri, URIRef("http://example.org/name"), Literal("John Doe")) in graph
    assert (person_uri, URIRef("http://example.org/worksFor"), org_uri) in graph
```

## Asynchronous Testing

For testing asynchronous code:

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_function():
    # Arrange
    data = {"key": "value"}
    
    # Act
    result = await async_process_data(data)
    
    # Assert
    assert result["processed"] == True
```

## Test Coverage

Aim for high test coverage:

- Unit tests: 80%+ coverage
- Integration tests: Focus on critical paths
- End-to-end tests: Cover main user workflows

Generate coverage reports:

```bash
pytest --cov=src --cov-report=html tests/
```

## Continuous Testing

Tests are run automatically in the CI pipeline:

- On pull requests
- On merges to development branch
- On release builds

See [CI/CD](ci-cd.md) for more details.

## Test Quality Metrics

Measure test quality using:

- **Coverage**: Percentage of code executed during tests
- **Mutation testing**: Tests' ability to detect bugs
- **Test execution time**: Tests should run quickly

## Debugging Tests

Tips for debugging failing tests:

```bash
# Run verbose output
pytest -vv tests/path/to/test.py

# Run with Python debugger on failure
pytest --pdb tests/path/to/test.py

# Run with detailed traceback
pytest --showlocals tests/path/to/test.py
```

## Best Practices

1. **Write Tests First**: Follow test-driven development when possible
2. **Keep Tests Simple**: Each test should test one thing
3. **Make Tests Fast**: Fast tests encourage frequent testing
4. **Isolate Tests**: Tests should not depend on each other
5. **Use Realistic Data**: Test with data that resembles production
6. **Test Edge Cases**: Include boundary conditions and error scenarios
7. **Maintain Tests**: Refactor tests as code evolves
8. **Review Test Code**: Apply the same quality standards to test code as to production code

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Python unittest Documentation](https://docs.python.org/3/library/unittest.html)
- [Testing Python Applications with pytest](https://semaphoreci.com/community/tutorials/testing-python-applications-with-pytest)
- [The Pragmatic Programmer](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/) (Chapter on Testing) 