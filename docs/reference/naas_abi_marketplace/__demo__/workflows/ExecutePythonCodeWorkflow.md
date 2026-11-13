# ExecutePythonCodeWorkflow

## What it is
- A development reference: a `Workflow` that executes provided Python code by writing it to a temporary directory of its own and running it in a separate interpreter via `subprocess.run`.
- Not a sandbox: the child runs on the host, as its user, with its filesystem and network. It gets none of the parent's environment (only `PATH`, `LANG`, `LC_ALL`, `TZ`, and `HOME` set to its directory), that directory as its working directory, and isolated mode (`-I`).
- No module agent carries it: served agents run code in the caller's coding workspace.
- Supports an execution timeout.

## Public API
- **`ExecutePythonCodeWorkflowConfiguration` (dataclass, `WorkflowConfiguration`)**
  - `timeout: int = 10` — subprocess timeout in seconds.

- **`ExecutePythonCodeWorkflowParameters` (`WorkflowParameters`)**
  - `code: str` — Python code to execute (`pydantic.Field` description: “Python code to execute”).

- **`ExecutePythonCodeWorkflow` (`Workflow`)**
  - `__init__(configuration: ExecutePythonCodeWorkflowConfiguration)`
    - Stores configuration.
  - `execute_python_code(parameters: ExecutePythonCodeWorkflowParameters) -> Any`
    - Behavior:
      - Runs `<sys.executable> -I <tempdir>/snippet.py` with `capture_output=True`, `text=True`, `timeout=<timeout>`, `cwd=<tempdir>` and the reduced environment above.
      - Return values:
        - On success (`returncode == 0`): returns `stdout.strip()` or `"Code executed successfully (no output)"`.
        - On failure: returns `"Error: <stderr.strip()>"`.
        - On timeout: returns `"Error: Code execution timed out after <timeout> seconds"`.
        - On other exceptions: returns `"Error: <exception message>"`.
      - Always deletes the temporary directory.
  - `as_tools() -> list[BaseTool]`
    - Returns a single LangChain `StructuredTool`:
      - `name="execute_python_code"`
      - `args_schema=ExecutePythonCodeWorkflowParameters`
      - Calls `execute_python_code(...)`.
  - `as_api(router: APIRouter, ...) -> None`
    - No-op; does not register any routes.

## Configuration/Dependencies
- Runs the current interpreter (`sys.executable`).
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
    ExecutePythonCodeWorkflowConfiguration(timeout=5)
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
- Code is executed as a normal subprocess (not sandboxed): never bind this workflow to an agent that other people use.
- `as_api(...)` is intentionally unimplemented (returns `None`).
