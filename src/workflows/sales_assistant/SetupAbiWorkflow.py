from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from pydantic import Field
from typing import Optional
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import subprocess
import os
from pathlib import Path

@dataclass
class SetupAbiWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for SetupAbiWorkflow.
    
    Attributes:
        base_dir (str): Base directory where ABI should be cloned
    """
    base_dir: str = str(Path.home())

class SetupAbiWorkflowParameters(WorkflowParameters):
    """Parameters for SetupAbiWorkflow execution.
    
    Attributes:
        github_username (str): GitHub username for cloning the repository
        branch (str): Branch to checkout. Defaults to main
    """
    github_username: str = Field(..., description="Your GitHub username")
    branch: str = Field("main", description="Branch to checkout (defaults to main)")

class SetupAbiWorkflow(Workflow):
    """Workflow to setup ABI locally by cloning the repository and configuring remotes."""
    
    __configuration: SetupAbiWorkflowConfiguration
    
    def __init__(self, configuration: SetupAbiWorkflowConfiguration):
        self.__configuration = configuration

    def run(self, parameters: SetupAbiWorkflowParameters) -> str:
        try:
            # Change to base directory
            os.chdir(self.__configuration.base_dir)
            
            # Clone the private repository
            clone_cmd = f"git clone https://github.com/{parameters.github_username}/abi-private.git"
            subprocess.run(clone_cmd, shell=True, check=True)
            
            # Change to repository directory
            os.chdir("abi-private")
            
            # Add upstream remote
            add_upstream_cmd = "git remote add upstream https://github.com/jupyter-naas/abi.git"
            subprocess.run(add_upstream_cmd, shell=True, check=True)
            
            # Pull from upstream with rebase
            pull_cmd = "git pull --rebase upstream main"
            subprocess.run(pull_cmd, shell=True, check=True)
            
            # Push to origin
            push_cmd = "git push"
            subprocess.run(push_cmd, shell=True, check=True)
            
            return "ABI setup completed successfully!"
            
        except subprocess.CalledProcessError as e:
            return f"Error during setup: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="setup_abi",
            description="Sets up ABI locally by cloning the repository and configuring remotes",
            func=lambda **kwargs: self.run(SetupAbiWorkflowParameters(**kwargs)),
            args_schema=SetupAbiWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/setup_abi")
        def setup_abi(parameters: SetupAbiWorkflowParameters):
            return self.run(parameters) 