# ExecutePythonCodeWorkflow

## What it is
- A `Workflow` that executes provided Python code by writing it to a temporary `.py` file and running it in a separate process via `subprocess.run`.
- Supports:
  - Execution timeout.
  - Optional blocking of `import`/`from` statements via a simple substring check.

## Public API
- **`ExecutePythonCodeWorkflowConfiguration` (dataclass, `WorkflowConfiguration`)**
  - `timeout: int = 10` — subprocess timeout in seconds.
  - `allow_imports: bool = True` — when `False`, rejects code containing `"import "` or `"from "`.

- **`ExecutePythonCodeWorkflowParameters` (`WorkflowParameters`)**
  - `code: str` — Python code to execute (`pydantic.Field` description: “Python code to execute”).

- **`ExecutePythonCodeWorkflow` (`Workflow`)**
  - `__init__(configuration: ExecutePythonCodeWorkflowConfiguration)`
    - Stores configuration.
  - `execute_python_code(parameters: ExecutePythonCodeWorkflowParameters) -> Any`
    - Behavior:
      - If `allow_imports=False` and code contains `"import "` or `"from "`, returns:  
        `"Error: Import statements are not allowed in this configuration"`
      - Runs `python <tempfile>` with `capture_output=True`, `text=True`, `timeout=<timeout>`.
      - Return values:
        - On success (`returncode == 0`): returns `stdout.strip()` or `"Code executed successfully (no output)"`.
        - On failure: returns `"Error: <stderr.strip()>"`.
        - On timeout: returns `"Error: Code execution timed out after <timeout> seconds"`.
        - On other exceptions: returns `"Error: <exception message>"`.
      - Always attempts to delete the temporary file.
  - `as_tools() -> list[BaseTool]`
    - Returns a single LangChain `StructuredTool`:
      - `name="execute_python_code"`
      - `args_schema=ExecutePythonCodeWorkflowParameters`
      - Calls `execute_python_code(...)`.
  - `as_api(router: APIRouter, ...) -> None`
    - No-op; does not register any routes.

## Configuration/Dependencies
- **Requires** a `python` executable on `PATH` (invoked as `subprocess.run(["python", temp_file_path], ...)`).
- **Key imports**
  - `fastapi.APIRouter` (only for typing in `as_api`)
  - `langchain_core.tools` (`BaseTool`, `StructuredTool`)
  - `naas_abi_core` (`logger`, `Workflow`, `WorkflowConfiguration`, `WorkflowParameters`)
  - `pydantic.Field`

## Usage
```python
from naas_abi_marketplace.__demo__.workflows.ExecutePythonCodeWorkflow import (
    ExecutePythonCodeWorkflow,
    ExecutePythonCodeWorkflowConfiguration,
    ExecutePythonCodeWorkflowParameters,
)

wf = ExecutePythonCodeWorkflow(
    ExecutePythonCodeWorkflowConfiguration(timeout=5, allow_imports=True)
)

out = wf.execute_python_code(
    ExecutePythonCodeWorkflowParameters(code="print('hello')")
)
print(out)  # "hello"
```

Using the LangChain tool wrapper:
```python
tool = wf.as_tools()[0]
print(tool.invoke({"code": "print(1 + 2)"}))  # "3"
```

## Caveats
- Code is executed as a normal subprocess (not sandboxed).
- The import restriction is a simple substring check and may be bypassed or yield false positives.
- `as_api(...)` is intentionally unimplemented (returns `None`).
