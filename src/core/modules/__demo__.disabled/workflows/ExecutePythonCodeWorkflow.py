from abi.workflow import Workflow, WorkflowConfiguration
from dataclasses import dataclass
from pydantic import Field
from abi import logger
from abi.workflow.workflow import WorkflowParameters
from langchain_core.tools import StructuredTool, BaseTool
from fastapi import APIRouter
from typing import Any, Annotated
import subprocess
import tempfile
import os
from enum import Enum

@dataclass
class ExecutePythonCodeWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for Python Code Execution Workflow.

    Attributes:
        timeout (int): Timeout in seconds for code execution
        allow_imports (bool): Whether to allow import statements
    """
    timeout: int = 10
    allow_imports: bool = True

class ExecutePythonCodeWorkflowParameters(WorkflowParameters):
    """Parameters for Python Code Execution Workflow.

    Attributes:
        code (str): Python code to execute
    """
    code: Annotated[str, Field(
        ..., 
        description="Python code to execute"
    )]

class ExecutePythonCodeWorkflow(Workflow):
    """Workflow for executing Python code safely."""

    __configuration: ExecutePythonCodeWorkflowConfiguration

    def __init__(
        self,
        configuration: ExecutePythonCodeWorkflowConfiguration,
    ):
        super().__init__(configuration)
        self.__configuration = configuration

    def execute_python_code(self, parameters: ExecutePythonCodeWorkflowParameters) -> Any:
        """
        Execute Python code safely.

        Args:
            parameters: Parameters containing the code to execute.

        Returns:
            str: Output from code execution or error message.
        """
        try:
            # Validate code if needed
            if not self.__configuration.allow_imports:
                if "import " in parameters.code or "from " in parameters.code:
                    return "Error: Import statements are not allowed in this configuration"

            # Create a temporary file to store the code
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
                temp_file.write(parameters.code.encode())
                temp_file_path = temp_file.name

            try:
                # Run the code in a separate process and capture output
                result = subprocess.run(
                    ["python", temp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=self.__configuration.timeout,
                )

                # Return stdout or stderr if there was an error
                if result.returncode == 0:
                    output = result.stdout.strip()
                    logger.info(f"Python code executed successfully. Output: {output}")
                    return output if output else "Code executed successfully (no output)"
                else:
                    error_msg = f"Error: {result.stderr.strip()}"
                    logger.error(f"Python code execution failed: {error_msg}")
                    return error_msg
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
        except subprocess.TimeoutExpired:
            error_msg = f"Error: Code execution timed out after {self.__configuration.timeout} seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error: {str(e)}"
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
                func=lambda **kwargs: self.execute_python_code(ExecutePythonCodeWorkflowParameters(**kwargs)),
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
        return None