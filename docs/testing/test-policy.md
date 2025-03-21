# ABI Super Assistant Test Policy

This document outlines the testing standards and practices for the ABI Super Assistant project.

## Test Categories

1. **Unit Tests**
   - Test individual components in isolation
   - Should be fast and not require external dependencies
   - Located in `tests/unit/`

2. **Integration Tests**
   - Test interactions between components
   - May use mocked external services
   - Located in `tests/integration/`

## Running Tests

- Run all tests with `make test`
- Run only unit tests with `make unit-tests`
- Run only integration tests with `make integration-tests`
- Run linting checks with `make lint`

## Test Requirements

- All new features must include appropriate test coverage
- Tests should be meaningful and test actual functionality
- Unit tests should be isolated and not depend on external state
- Integration tests should use test fixtures for external dependencies

## CI Integration

Tests are automatically run in CI on:
- Every pull request
- Merges to the main branch
- Release tagging

## Test Dependencies

Test-specific dependencies should be specified in the project's `pyproject.toml` under the `[tool.poetry.dev-dependencies]` section. 