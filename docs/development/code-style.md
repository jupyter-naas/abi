# Code Style Guide

This document outlines the coding standards and style guidelines for the ABI framework. Following these guidelines ensures code consistency, readability, and maintainability across the project.

## General Principles

- **Readability**: Code should be easy to read and understand.
- **Simplicity**: Prefer simple solutions over complex ones.
- **Consistency**: Follow established patterns and conventions.
- **Documentation**: Document code thoroughly, especially public interfaces.
- **Testing**: Write tests for all code functionality.

## Python Style Guidelines

ABI follows [PEP 8](https://pep8.org/) with some customizations. We use tools like `black`, `flake8`, `isort`, and `mypy` to enforce style guidelines.

### Code Formatting

- **Line Length**: Maximum 88 characters (Black default)
- **Indentation**: 4 spaces (no tabs)
- **Line Endings**: Unix-style (LF)
- **Encoding**: UTF-8

### Naming Conventions

- **Modules**: Lowercase with underscores (`my_module.py`)
- **Packages**: Lowercase without underscores (`package`)
- **Classes**: PascalCase (`MyClass`)
- **Functions/Methods**: snake_case (`my_function`)
- **Variables**: snake_case (`my_variable`)
- **Constants**: UPPERCASE with underscores (`MY_CONSTANT`)
- **Private Attributes**: Prefix with underscore (`_private_variable`)

### Imports

- Sort imports using `isort`
- Group imports in the following order:
  1. Standard library imports
  2. Related third-party imports
  3. Local application/library specific imports
- Use absolute imports rather than relative imports

Example:
```python
# Standard library imports
import os
import sys
from typing import List, Dict, Optional

# Third-party imports
import numpy as np
import pandas as pd

# Local imports
from abi.utils import helpers
from abi.models import User
```

### Documentation

- Use Google-style docstrings:

```python
def calculate_average(numbers: List[float]) -> float:
    """Calculate the average of a list of numbers.
    
    Args:
        numbers: A list of numbers to average
        
    Returns:
        The average value
        
    Raises:
        ValueError: If the list is empty
    """
    if not numbers:
        raise ValueError("Cannot calculate average of empty list")
    return sum(numbers) / len(numbers)
```

- Document all public classes, methods, and functions
- Include type hints for parameters and return values
- Document exceptions that may be raised
- Provide examples for complex operations

### Comments

- Write comments that explain why, not what
- Keep comments up to date with code changes
- Use TODO comments for temporary, non-critical deficiencies:
  ```python
  # TODO: Optimize this algorithm for better performance
  ```

### Type Hints

- Use type hints consistently throughout the codebase
- Use `Optional[T]` instead of `Union[T, None]` or `T | None`
- Use the most specific type possible (e.g., `List[str]` instead of just `List`)
- Use `Any` sparingly, only when truly necessary

```python
from typing import Dict, List, Optional, Union

def process_data(data: List[Dict[str, Union[str, int]]]) -> Optional[str]:
    """Process a list of data dictionaries."""
    pass
```

### Class Design

- Follow the single responsibility principle
- Use dataclasses for data containers:

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Customer:
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    addresses: List[str] = field(default_factory=list)
```

- Prefer composition over inheritance
- Make attributes private unless they need to be accessed externally

### Function Design

- Functions should do one thing well
- Keep functions reasonably short (under 50 lines when possible)
- Use keyword arguments for clarity in function calls
- Use default arguments for optional parameters
- Return explicit values rather than modifying parameters

## Component-Specific Guidelines

### Assistants

- Keep system messages in separate configuration files
- Use structured response formatting
- Handle errors gracefully with user-friendly messages

### Integrations

- Follow the established integration pattern
- Implement proper error handling and retries
- Use mock interfaces for testing

```python
class SomeIntegration(Integration):
    def __init__(self, configuration: SomeIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        # Setup code here
```

### Pipelines

- Implement clear input validation
- Document input and output formats
- Use a consistent graph building approach

```python
def run(self, parameters: SomePipelineParameters) -> Graph:
    # Validate parameters
    self._validate_parameters(parameters)
    
    # Initialize graph
    graph = ABIGraph()
    
    # Process data
    # ...
    
    # Return or persist the graph
    return graph
```

### Workflows

- Clearly separate business logic from implementation details
- Document all workflow steps
- Implement proper logging

### Ontology

- Follow W3C semantic web standards
- Use consistent terminology
- Document classes and properties thoroughly

## JavaScript/TypeScript Style Guidelines

For frontend components, we follow [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript) with some customizations.

### Code Formatting

- **Line Length**: Maximum 100 characters
- **Semicolons**: Required
- **Quotes**: Single quotes for JavaScript, double quotes for JSX/HTML
- **Indentation**: 2 spaces

### React Components

- Use functional components with hooks
- Keep components focused on a single responsibility
- Use prop types or TypeScript for type checking

```tsx
import React, { useState } from 'react';
import PropTypes from 'prop-types';

const UserProfile: React.FC<UserProfileProps> = ({ username, email }) => {
  const [isActive, setIsActive] = useState(false);
  
  return (
    <div className="user-profile">
      <h2>{username}</h2>
      <p>{email}</p>
      <button onClick={() => setIsActive(!isActive)}>
        {isActive ? 'Deactivate' : 'Activate'}
      </button>
    </div>
  );
};

UserProfile.propTypes = {
  username: PropTypes.string.isRequired,
  email: PropTypes.string.isRequired,
};

export default UserProfile;
```

## SQL Style Guidelines

- Use uppercase for SQL keywords
- Use snake_case for table and column names
- Include comments for complex queries
- Format queries for readability:

```sql
SELECT 
    u.id,
    u.username,
    COUNT(o.id) AS order_count
FROM 
    users u
LEFT JOIN 
    orders o ON u.id = o.user_id
WHERE 
    u.status = 'active'
    AND u.created_at > '2022-01-01'
GROUP BY 
    u.id, u.username
HAVING 
    COUNT(o.id) > 5
ORDER BY 
    order_count DESC
LIMIT 
    100;
```

## YAML Style Guidelines

- Use 2 space indentation
- Use snake_case for keys
- Include comments for clarification
- Keep lines under 80 characters when possible

```yaml
# Authentication configuration
auth:
  # JWT settings
  jwt:
    secret: ${JWT_SECRET}
    expiration: 3600  # in seconds
  # OAuth providers
  oauth:
    # Google OAuth settings
    google:
      client_id: ${GOOGLE_CLIENT_ID}
      client_secret: ${GOOGLE_CLIENT_SECRET}
```

## Code Linting and Formatting

We use several tools to ensure code quality and consistency:

### Python

- **Black**: For code formatting
- **Flake8**: For style guide enforcement
- **isort**: For import sorting
- **mypy**: For static type checking

Configuration is in `pyproject.toml` and `.flake8`.

### JavaScript/TypeScript

- **ESLint**: For code linting
- **Prettier**: For code formatting

Configuration is in `.eslintrc.js` and `.prettierrc`.

## Pre-commit Hooks

We use pre-commit hooks to automatically check code before committing:

```bash
pre-commit install
```

The pre-commit configuration is in `.pre-commit-config.yaml`.

## Manual Code Reviews

In addition to automated checks, code reviews should focus on:

- Logical correctness
- Architectural concerns
- Performance considerations
- Security implications
- Documentation completeness
- Test coverage

## Commit Message Guidelines

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types include:
- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation changes
- **style**: Changes that don't affect code functionality
- **refactor**: Code changes that neither fix bugs nor add features
- **test**: Adding or correcting tests
- **chore**: Changes to the build process or tools

Example:
```
feat(auth): add OAuth support for GitHub

Implemented GitHub OAuth provider to allow users to login with their
GitHub accounts.

Closes #123
```

## Additional Resources

- [PEP 8](https://pep8.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Clean Code by Robert C. Martin](https://www.oreilly.com/library/view/clean-code-a/9780136083238/) 