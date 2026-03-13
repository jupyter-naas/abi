# Test Python Scripts

Testing is the key to maintainability of each project. This guide covers how to write and run tests using pytest in this project.

## Naming Convention

We use the suffix `_test.py` to name all our test files. 
To make it more convenient, we place test files next to the main files so they are easy to find, check, and update.

**Examples:**
- `Agent.py` → `Agent_test.py`
- `Workflow.py` → `Workflow_test.py` 
- `Pipeline.py` → `Pipeline_test.py`

## Project Structure

```
src/
├── custom/
│   └── modules/
│       └── mymodule/
│           └── agents/
│               ├── Agent.py
│               └── Agent_test.py
│           └── workflows/
│               ├── Workflow.py
│               └── Workflow_test.py
│           └── pipelines/
│               ├── Pipeline.py
│               └── Pipeline_test.py
```

## Writing Tests

We use the pytest library for testing. You can use the `@pytest.fixture` decorator to set up initial configurations and reusable test data.

### Basic Test Example

```python
import pytest
from src.custom.mymodule.calculator import Calculator

@pytest.fixture
def calculator():
    """Fixture that returns a Calculator instance"""
    return Calculator()

def test_addition(calculator):
    """Test the add method of Calculator"""
    result = calculator.add(2, 3)
    assert result == 5

def test_subtraction(calculator):
    """Test the subtract method of Calculator"""
    result = calculator.subtract(5, 3) 
    assert result == 2

def test_multiplication(calculator):
    """Test the multiply method of Calculator"""
    result = calculator.multiply(4, 3)
    assert result == 12

def test_division(calculator):
    """Test the divide method of Calculator"""
    result = calculator.divide(10, 2)
    assert result == 5
    
    # Test division by zero
    with pytest.raises(ValueError):
        calculator.divide(5, 0)
```

### Advanced Test Examples

#### Testing with Multiple Fixtures

```python
import pytest
from src.custom.mymodule.data_processor import DataProcessor

@pytest.fixture
def sample_data():
    """Fixture that provides sample data for testing"""
    return [1, 2, 3, 4, 5]

@pytest.fixture
def data_processor():
    """Fixture that returns a DataProcessor instance"""
    return DataProcessor()

def test_process_data(data_processor, sample_data):
    """Test data processing with sample data"""
    result = data_processor.process(sample_data)
    assert len(result) == 5
    assert result[0] == 2  # Assuming processing doubles the values
```

#### Testing Exceptions

```python
import pytest
from src.custom.mymodule.calculator import Calculator

@pytest.fixture
def calculator():
    """Fixture that returns a Calculator instance"""
    return Calculator()

def test_invalid_input(calculator):
    """Test that invalid inputs raise appropriate exceptions"""
    with pytest.raises(TypeError):
        calculator.add("string", 5)
    
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        calculator.divide(10, 0)
```

#### Parametrized Tests

```python
import pytest

@pytest.mark.parametrize("a, b, expected", [
    (2, 3, 5),
    (0, 0, 0),
    (-1, 1, 0),
    (100, 200, 300),
])
def test_addition_parametrized(calculator, a, b, expected):
    """Test addition with multiple input combinations"""
    result = calculator.add(a, b)
    assert result == expected
```

## Running Tests

### Running a Specific Test File

```bash
uv run python -m pytest src/custom/modules/your_module_name/pipelines/your_pipeline_name_test.py
```

### Running All Tests

```bash
# Run all tests in the project
uv run python -m pytest

# Run tests with verbose output
uv run python -m pytest -v

# Run tests and show print statements
uv run python -m pytest -s
```

### Running Tests with Specific Options

```bash
# Run tests matching a pattern
uv run python -m pytest -k "test_addition"

# Run tests in a specific directory
uv run python -m pytest src/custom/modules/mymodule/

# Run tests and generate coverage report
uv run python -m pytest --cov=src/custom/modules/mymodule

# Run tests and stop on first failure
uv run python -m pytest -x

# Run tests in parallel (requires pytest-xdist)
uv run python -m pytest -n auto
```

## Test Output

The test runner will show:
- Number of tests collected
- Number of tests passed/failed
- Detailed error messages for failed tests
- Test execution time

**Example output:**
```
============================= test session starts ==============================
platform linux -- Python 3.9.7, pytest-6.2.5, py-1.10.0, pluggy-0.13.1
rootdir: /home/user/project
collected 4 items

src/custom/modules/mymodule/calculator_test.py ....                    [100%]

============================== 4 passed in 0.02s ==============================
```

## Best Practices

### 1. Test Organization
- Keep test files close to the code they test
- Use descriptive test function names
- Group related tests in the same file

### 2. Fixtures
- Use fixtures for setup and teardown
- Keep fixtures simple and focused
- Use fixture scope appropriately (`function`, `class`, `module`, `session`)

### 3. Assertions
- Use specific assertions (`assert result == expected`)
- Test both positive and negative cases
- Test edge cases and error conditions

### 4. Test Data
- Use realistic test data
- Avoid hardcoded values when possible
- Use parametrized tests for multiple scenarios

### 5. Documentation
- Write clear docstrings for test functions
- Explain what each test is verifying
- Document any special setup requirements

## Common pytest Options

| Option | Description |
|--------|-------------|
| `-v` | Verbose output |
| `-s` | Show print statements |
| `-k "pattern"` | Run tests matching pattern |
| `-x` | Stop on first failure |
| `--tb=short` | Short traceback format |
| `--cov` | Generate coverage report |
| `-n auto` | Run tests in parallel |

## Troubleshooting

### Test Discovery Issues
If pytest doesn't find your tests:
1. Ensure test files end with `_test.py`
2. Check that test functions start with `test_`
3. Verify the file is in the correct directory

### Import Errors
If you get import errors:
1. Make sure your `PYTHONPATH` includes the project root
2. Use absolute imports in test files
3. Check that the module you're testing is properly installed

### Fixture Issues
If fixtures aren't working:
1. Ensure the fixture function is decorated with `@pytest.fixture`
2. Check that the fixture name matches the parameter name
3. Verify the fixture is in scope (same file or conftest.py)