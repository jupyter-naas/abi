from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass
from pydantic import Field
from typing import Dict, List
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import os
from abi import logger

@dataclass
class SetupGithubABIWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for SetupGithubABIWorkflows.
    
    Attributes:
        github_integration_config (GithubIntegrationConfiguration): Configuration for GitHub integration
    """
    github_integration_config: GithubIntegrationConfiguration

class CreateGitHubPrivateForkParameters(WorkflowParameters):
    """Parameters for CreateGitHubPrivateFork execution."""
    org_name: str = Field(description="The organization to create the repository in")
    repository_name: str = Field(description="The name of the repository to create a private fork of")
    repository_description: str = Field(description="The description of the repository")

class CloneGitHubRepositoryParameters(WorkflowParameters):
    """Parameters for CloneGitHubRepository execution."""
    repo_name: str = Field(description="The name of the repository to clone in format: owner/name")

class UpdateRepoSecretsParameters(WorkflowParameters):
    """Parameters for UpdateRepoSecrets execution."""
    repository_name: str = Field(description="The name of the repository to update secrets for")
    secrets: Dict[str, str] = Field(description="Dictionary of secret name-value pairs to update")

class SetupGithubABIWorkflows(Workflow):
    """Workflows for setting up GitHub repositories and managing secrets for ABI."""
    
    __configuration: SetupGithubABIWorkflowsConfiguration
    
    def __init__(self, configuration: SetupGithubABIWorkflowsConfiguration):
        self.__configuration = configuration
        self.__github = GithubIntegration(self.__configuration.github_integration_config)

    def create_github_private_fork(self, parameters: CreateGitHubPrivateForkParameters) -> str:
        """Creates a private fork of the ABI repository.
        
        Args:
            parameters: Parameters containing repository name and description
            
        Returns:
            str: Success message with clone URL
        """
        # Check if repository already exists
        try:
            repo = self.__github.get_repository_details(f"{parameters.org_name}/{parameters.repository_name}")
            if repo:
                message = f"Repository {parameters.repository_name} already exists in organization {parameters.org_name}"
                return message
        except:
            # Create private repository via GitHub API if it doesn't exist
            repo = self.__github.create_organization_repository(
                org=parameters.org_name,
                name=parameters.repository_name,
                description=parameters.repository_description,
                private=True
            )
        full_repo_name = repo.get("full_name")
        
        # Clone repository locally
        os.chdir("..")
        clone_url = f"https://github.com/{full_repo_name}.git"
        os.system(f"git clone {clone_url}")
        os.chdir(parameters.repository_name)
        
        # Add upstream and sync
        os.system("git remote add upstream https://github.com/jupyter-naas/abi.git")
        os.system("git pull --rebase upstream main")
        os.system("git push")
        
        # Copy and edit config files
        os.system("cp .env.example .env")
        os.system("cp config.yaml.example config.yaml")
        
        # Return to original directory
        os.chdir("..")
        return f"Successfully created private fork at {clone_url}. Please edit .env and config.yaml with your configuration."
    
    def clone_github_repository_setup_remote(self, parameters: CloneGitHubRepositoryParameters) -> str:
        """Clones a GitHub repository.
        
        Args:
            parameters: Parameters containing repository name and description
            
        Returns:
            str: Success message with clone URL
        """
        # Clone repository locally
        os.chdir("..")
        clone_url = f"https://github.com/{parameters.repo_name}.git"
        os.system(f"git clone {clone_url}")
        os.chdir(parameters.repository_name)

        # Add upstream and sync
        os.system("git remote add upstream https://github.com/jupyter-naas/abi.git")
        os.system("git pull --rebase upstream main")
        return f"Successfully cloned repository {parameters.repository_name} and added upstream remote."

    def update_repo_secrets(self, parameters: UpdateRepoSecretsParameters) -> List[str]:
        """Updates GitHub repository secrets.
        
        Args:
            parameters: Parameters containing repository name and secrets dictionary
            
        Returns:
            List[str]: List of success messages for each secret updated
        """
        results = []
        for secret_name, secret_value in parameters.secrets.items():
            self.__github.create_or_update_repository_secret(
                repo_name=parameters.repository_name,
                secret_name=secret_name,
                secret_value=secret_value
            )
            results.append(f"Successfully updated secret '{secret_name}' in repository '{parameters.repository_name}'")
        return results

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="create_github_private_fork",
                description="Create a private fork of the ABI repository",
                func=lambda org_name, repository_name, repository_description: self.create_github_private_fork(CreateGitHubPrivateForkParameters(org_name=org_name, repository_name=repository_name, repository_description=repository_description)),
                args_schema=CreateGitHubPrivateForkParameters
            ),
            StructuredTool(
                name="clone_github_repository_setup_remote",
                description="Clone a GitHub repository and setup the remote",
                func=lambda repo_name: self.clone_github_repository_setup_remote(CloneGitHubRepositoryParameters(repo_name=repo_name)),
                args_schema=CloneGitHubRepositoryParameters
            ),
            StructuredTool(
                name="update_repo_secrets",
                description="Update GitHub repository secrets",
                func=lambda repository_name, secrets: self.update_repo_secrets(UpdateRepoSecretsParameters(repository_name=repository_name, secrets=secrets)),
                args_schema=UpdateRepoSecretsParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/create_github_fork")
        def create_fork(parameters: CreateGitHubPrivateForkParameters):
            return self.create_github_private_fork(parameters)
            
        @router.post("/update_secrets")
        def update_secrets(parameters: UpdateRepoSecretsParameters):
            return self.update_repo_secrets(parameters) 