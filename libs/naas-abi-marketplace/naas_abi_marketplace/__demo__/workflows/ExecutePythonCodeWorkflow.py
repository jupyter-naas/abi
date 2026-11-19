"""Run a Python snippet in a child interpreter: a development reference.

This is not a sandbox. The child runs on the host, as the host's user, with its
filesystem and network. It gets none of the parent's environment (secrets live
there), a temporary working directory of its own and isolated mode (``-I``), but
nothing more. No module agent carries this workflow: served agents run code in
the caller's coding workspace.
"""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any

from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field

# The only variables the child sees: enough to find an interpreter and decode text.
_CHILD_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "TZ")


@dataclass
class ExecutePythonCodeWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for Python Code Execution Workflow.

    Attributes:
        timeout (int): Timeout in seconds for code execution
    """

    timeout: int = 10


class ExecutePythonCodeWorkflowParameters(WorkflowParameters):
    """Parameters for Python Code Execution Workflow.

    Attributes:
        code (str): Python code to execute
    """

    code: Annotated[str, Field(..., description="Python code to execute")]


class ExecutePythonCodeWorkflow(Workflow):
    """Runs a Python snippet in a child interpreter (see the module docstring)."""

    __configuration: ExecutePythonCodeWorkflowConfiguration

    def __init__(
        self,
        configuration: ExecutePythonCodeWorkflowConfiguration,
    ):
        super().__init__(configuration)
        self.__configuration = configuration

    def execute_python_code(
        self, parameters: ExecutePythonCodeWorkflowParameters
    ) -> Any:
        """
        Execute Python code in a child interpreter without the parent's environment.

        Args:
            parameters: Parameters containing the code to execute.

        Returns:
            str: Output from code execution or error message.
        """
        try:
            with tempfile.TemporaryDirectory(prefix="python-code-") as workdir:
                script = os.path.join(workdir, "snippet.py")
                with open(script, "w", encoding="utf-8") as handle:
                    handle.write(parameters.code)
                env = {k: os.environ[k] for k in _CHILD_ENV_KEYS if k in os.environ}
                env["HOME"] = workdir
                # Run the code in a separate process and capture output
                result = subprocess.run(
                    [sys.executable, "-I", script],
                    capture_output=True,
                    text=True,
                    timeout=self.__configuration.timeout,
                    cwd=workdir,
                    env=env,
                    check=False,
                )

            # Return stdout or stderr if there was an error
            if result.returncode == 0:
                output = result.stdout.strip()
                logger.info(f"Python code executed successfully. Output: {output}")
                return output if output else "Code executed successfully (no output)"
            error_msg = f"Error: {result.stderr.strip()}"
            logger.error(f"Python code execution failed: {error_msg}")
            return error_msg
        except subprocess.TimeoutExpired:
            error_msg = f"Error: Code execution timed out after {self.__configuration.timeout} seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error: {e!s}"
            logger.error(f"Unexpected error during code execution: {error_msg}")
            return error_msg

    def as_tools(self) -> list[BaseTool]:
        """
        Return a list of tools that can be used to interact with this workflow.

        Returns:
            list[StructuredTool]: List of tools
        """
        return [
            StructuredTool(
                name="execute_python_code",
                description="Execute Python code and return the result.",
                func=lambda **kwargs: self.execute_python_code(
                    ExecutePythonCodeWorkflowParameters(**kwargs)
                ),
                args_schema=ExecutePythonCodeWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
