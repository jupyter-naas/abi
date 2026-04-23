# ExecutePythonCodeWorkflow

## What it is
- A `Workflow` implementation that executes provided Python code in a separate process (`subprocess.run`) using a temporary `.py` file.
- Supports a configurable execution timeout and an optional restriction on `import` usage.

## Public API
- **`ExecutePythonCodeWorkflowConfiguration` (dataclass)**
  - `timeout: int = 10` — max execution time (seconds) for the subprocess.
  - `allow_imports: bool = True` — if `False`, rejects code containing `"import "` or `"from "`.

- **`ExecutePythonCodeWorkflowParameters` (pydantic/WorkflowParameters)**
  - `code: str` — Python code to execute.

- **`ExecutePythonCodeWorkflow` (Workflow)**
  - `execute_python_code(parameters: ExecutePythonCodeWorkflowParameters) -> Any`
    - Writes `parameters.code` to a temporary `.py` file, runs `python <tempfile>`, and returns:
      - stdout (trimmed) when exit code is `0`,
      - `"Code executed successfully (no output)"` when stdout is empty and exit code is `0`,
      - `"Error: <stderr>"` when exit code is non-zero,
      - `"Error: Code execution timed out after <timeout> seconds"` on timeout,
      - `"Error: <exception message>"` for other exceptions.
    - Always attempts to delete the temporary file.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named `execute_python_code` with `ExecutePythonCodeWorkflowParameters` as the args schema.
  - `as_api(router: APIRouter, ...) -> None`
    - Currently a no-op (returns `None` and does not register routes).

## Configuration/Dependencies
- **Runtime dependencies**
  - Requires `python` to be available on `PATH` (invoked as `subprocess.run(["python", temp_file_path], ...)`).
- **Libraries**
  - Uses `fastapi` (only for type in `as_api`), `langchain_core.tools`, `pydantic`, and `naas_abi_core` (`Workflow`, `WorkflowConfiguration`, `WorkflowParameters`, `logger`).

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

result = wf.execute_python_code(
    ExecutePythonCodeWorkflowParameters(code="print('hello')")
)
print(result)  # -> "hello"
```

Using the tool wrapper:
```python
tool = wf.as_tools()[0]
print(tool.invoke({"code": "print(1 + 2)"}))  # -> "3"
```

## Caveats
- **Not a sandbox**: code is executed as a normal Python subprocess and can perform arbitrary operations (file system, network, etc.) unless constrained externally.
- **Import restriction is heuristic**: when `allow_imports=False`, it only checks for substring occurrences of `"import "` or `"from "` and may be bypassed or produce false positives.
- **API integration is unimplemented**: `as_api(...)` does not register any FastAPI routes.
