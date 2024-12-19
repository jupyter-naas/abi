from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.integrations.AWSS3Integration import AWSS3Integration, AWSS3IntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from typing import List, Dict, Any, Optional, BinaryIO, Union
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
import os
from fastapi import UploadFile
from fastapi.responses import StreamingResponse
import io
import glob

@dataclass
class NaasStorageWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for NaasStorageWorkflows.
    
    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for Naas integration
    """
    naas_integration_config: NaasIntegrationConfiguration

class ListNaasStorageParameters(WorkflowParameters):
    """Parameters for listing Naas storage.
    
    Attributes:
        workspace_id (str): ID of the workspace to list storage from
    """
    workspace_id: str = Field(..., description="ID of the workspace to list storage from")

class CreateNaasStorageParameters(WorkflowParameters):
    """Parameters for creating a new Naas storage.
    
    Attributes:
        workspace_id (str): ID of the workspace to create storage in
        storage_name (str): Name of the storage to create
    """
    workspace_id: str = Field(..., description="ID of the workspace to create storage in")
    storage_name: str = Field(..., description="Name of the storage to create")

class ListNaasStorageFilesParameters(WorkflowParameters):
    """Parameters for ListNaasStorageFiles execution.
    
    Attributes:
        workspace_id (str): ID of the workspace containing the storage
        storage_name (str): Name of the storage to list files from
        prefix (str, optional): Directory prefix to list objects under
    """
    workspace_id: str = Field(..., description="ID of the workspace containing the storage")
    storage_name: str = Field(..., description="Name of the storage to list files from")

class DownloadNaasStorageFileParameters(WorkflowParameters):
    """Parameters for downloading a file from Naas storage.
    
    Attributes:
        workspace_id (str): ID of the workspace containing the storage
        storage_name (str): Name of the storage to download from
        remote_path (str): Path to the file within the storage
        local_path (str): Destination path to download the file to
    """
    workspace_id: str = Field(..., description="ID of the workspace containing the storage")
    storage_name: str = Field(..., description="Name of the storage to download from")
    remote_path: str = Field(..., description="Path to the file within the storage")
    local_path: str = Field(..., description="Destination path to download the file to")

class DownloadAllFilesFromNaasStorageParameters(WorkflowParameters):
    """Parameters for downloading all files from Naas storage.
    
    Attributes:
        workspace_id (str): ID of the workspace containing the storage
        storage_name (str): Name of the storage to download from
        remote_directory_path (str): Path to the directory within the storage to download from
        local_directory_path (str): Destination directory path to download the files to
    """
    workspace_id: str = Field(..., description="ID of the workspace containing the storage")
    storage_name: str = Field(..., description="Name of the storage to download from")
    local_directory_path: Optional[str] = Field(..., description="Destination directory path to download the files to")

class UploadNaasStorageFileParameters(WorkflowParameters):
    """Parameters for uploading a file to Naas storage.
    
    Attributes:
        workspace_id (str): ID of the workspace containing the storage
        storage_name (str): Name of the storage to upload to
        local_path (str): Source path to upload from
    """
    workspace_id: str = Field(..., description="ID of the workspace containing the storage")
    storage_name: str = Field(..., description="Name of the storage to upload to")
    local_path: str = Field(..., description="Source path to upload from")

class UploadAllFilesFromLocalDirectoryParameters(WorkflowParameters):
    """Parameters for uploading all files from a local directory to Naas storage.
    
    Attributes:
        workspace_id (str): ID of the workspace containing the storage
        storage_name (str): Name of the storage to upload to
        local_directory_path (str): Source directory path to upload from
    """
    workspace_id: str = Field(..., description="ID of the workspace containing the storage")
    storage_name: str = Field(..., description="Name of the storage to upload to")
    local_directory_path: str = Field(..., description="Source directory path to upload from")

class GetCurrentDirectoryParameters(WorkflowParameters):
    """Parameters for getting the current directory.
    
    Attributes:
        None
    """
    pass

class ListFilesInCurrentDirectoryParameters(WorkflowParameters):
    """Parameters for listing files in the current directory.
    
    Attributes:
        None
    """
    pass

class NaasStorageWorkflows(Workflow):
    """Workflow for listing files in a Naas storage location."""
    __configuration: NaasStorageWorkflowsConfiguration
    
    def __init__(self, configuration: NaasStorageWorkflowsConfiguration):
        self.__configuration = configuration
        self.__naas = NaasIntegration(self.__configuration.naas_integration_config)

    def _get_s3_client(self, workspace_id: str, storage_name: str) -> tuple[AWSS3Integration, str, str]:
        """Helper method to initialize S3 client and get bucket info."""
        credentials = self.__naas.get_storage_credentials(
            workspace_id=workspace_id,
            storage_name=storage_name
        )
        
        if not credentials:
            raise ValueError("Failed to get storage credentials")

        # Extract S3 credentials
        creds = credentials.get("credentials", {}).get("s3", {})
        s3_config = AWSS3IntegrationConfiguration(
            aws_access_key_id=creds.get("access_key_id"),
            aws_secret_access_key=creds.get("secret_key"),
            session_token=creds.get("session_token"),
            region_name=creds.get("region_name")
        )
        
        # Parse bucket info
        endpoint_url = creds.get("endpoint_url")
        bucket_name = endpoint_url.split("s3://")[1].split("/")[0]
        bucket_prefix = endpoint_url.split(f"{bucket_name}/")[1]
        
        return AWSS3Integration(s3_config), bucket_name, bucket_prefix
    
    def create_storage(self, parameters: CreateNaasStorageParameters) -> bool:
        """Creates a new storage in a Naas workspace.
        
        Args:
            parameters: CreateNaasStorageParameters containing workspace_id and storage_name
            
        Returns:
            bool: True if storage was created successfully
        """
        return self.__naas.create_workspace_storage(parameters.workspace_id, parameters.storage_name)
    
    def list_storage(self, parameters: ListNaasStorageParameters) -> List[Dict[str, Any]]:
        """Lists storage in a Naas workspace.
        
        Args:
            parameters: ListNaasStorageParameters containing workspace_id
            
        Returns:
            List[Dict[str, Any]]: List of storage information
        """
        return self.__naas.list_workspace_storage(parameters.workspace_id)
    
    def list_files_from_naas_storage(self, parameters: ListNaasStorageFilesParameters) -> List[Dict[str, Any]]:
        """Lists files in a Naas storage location using AWS S3.
        
        Args:
            parameters: ListNaasStorageFilesParameters containing workspace_id, storage_name, and optional prefix
            
        Returns:
            List[Dict[str, Any]]: List of file information including keys, sizes, and last modified dates
        """
        s3_client, bucket_name, bucket_prefix = self._get_s3_client(
            parameters.workspace_id, 
            parameters.storage_name
        )

        # Combine storage prefix with user-provided prefix
        full_prefix = os.path.join(bucket_prefix) + "/"
        logger.info(f"Full prefix: {full_prefix}")
        
        # List objects using S3 client
        files = []
        try:
            objects = s3_client.list_objects(
                bucket=bucket_name,
                prefix=full_prefix
            )
            files = [object.get("key") for object in objects if not object.get("key").endswith("/")]
            logger.info(f"Files: {len(files)}")
            return files
        except Exception as e:
            logger.error(f"Error listing S3 objects: {str(e)}")
            return []

    def download_file_to_local(self, parameters: DownloadNaasStorageFileParameters) -> BinaryIO:
        """Downloads a file from Naas storage.
        
        Args:
            parameters: Parameters containing workspace_id, storage_name, and file_path
            
        Returns:
            BinaryIO: File content as a binary stream
        """
        s3_client, bucket_name, bucket_prefix = self._get_s3_client(
            parameters.workspace_id, 
            parameters.storage_name
        )
        remote_path = parameters.remote_path.replace(bucket_prefix, "")
        full_path = os.path.join(bucket_prefix, remote_path)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(parameters.local_path), exist_ok=True)
        
        return s3_client.download_file(bucket_name, full_path, parameters.local_path)
    
    def download_all_files_from_naas_storage(self, parameters: DownloadAllFilesFromNaasStorageParameters) -> str:
        """Downloads all files from a Naas storage location.
        
        Args:
            parameters: Parameters containing workspace_id, storage_name, and remote_directory_path
            
        Returns:
            bool: True if download was successful
        """
        s3_client, bucket_name, bucket_prefix = self._get_s3_client(
            parameters.workspace_id, 
            parameters.storage_name
        )
        files = self.list_files_from_naas_storage(workspace_id=parameters.workspace_id, storage_name=parameters.storage_name)
        
        # Create base directory if it doesn't exist
        logger.info(f"Local directory path: {parameters.local_directory_path}")
        if parameters.local_directory_path: 
            os.makedirs(parameters.local_directory_path, exist_ok=True)
            logger.info(f"Created local directory: {parameters.local_directory_path}")
        
        files_downloaded = 0
        for file in files:
            if parameters.local_directory_path:
                local_path = os.path.join(parameters.local_directory_path, file.split(bucket_prefix)[-1])
            else:
                local_path = file.split(bucket_prefix)[-1]
            # Create subdirectories if needed
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            logger.info(f"Downloading file: {file} to {local_path}")
            s3_client.download_file(bucket_name, file, local_path)
            files_downloaded += 1
            logger.info(f"Downloaded file: {file} to {local_path}")
        return f"Downloaded {files_downloaded} files to {parameters.local_directory_path}"

    def upload_file_from_local(self, parameters: UploadNaasStorageFileParameters) -> bool:
        """Uploads a file to Naas storage.
        
        Args:
            parameters: Parameters containing workspace_id, storage_name, file_path and content
            
        Returns:
            bool: True if upload was successful
        """
        s3_client, bucket_name, bucket_prefix = self._get_s3_client(
            parameters.workspace_id, 
            parameters.storage_name
        )
        return s3_client.upload_file(parameters.local_path, bucket_name, bucket_prefix, parameters.local_path)
    
    def upload_all_files_from_local_directory(self, parameters: UploadNaasStorageFileParameters) -> bool:
        """Uploads all files from a local directory to Naas storage.
        
        Args:
            parameters: Parameters containing workspace_id, storage_name, and file_path
            
        Returns:
            bool: True if upload was successful
        """
        s3_client, bucket_name, bucket_prefix = self._get_s3_client(
            parameters.workspace_id, 
            parameters.storage_name
        )
        files_to_upload = glob.glob(os.path.join(parameters.local_directory_path, '**', '*'), recursive=True)
        logger.info(f"Files to upload: {len(files_to_upload)}")
        files_uploaded = 0
        for file in files_to_upload:
            if os.path.isfile(file):  # Only upload if it's a file, not a directory
                s3_client.upload_file(file, bucket_name, bucket_prefix, file)
                files_uploaded += 1
                logger.info(f"Uploaded file: {file}")
        return files_uploaded
    
    def get_current_directory(self, parameters: GetCurrentDirectoryParameters) -> str:
        """Gets the current directory.
        
        Args:
            parameters: Parameters containing workspace_id, storage_name, and file_path
            
        Returns:
            str: Current directory
        """
        return os.getcwd()
    
    def list_files_in_current_directory(self, parameters: ListFilesInCurrentDirectoryParameters) -> str:
        """Lists files in the current directory.
        
        Args:
            parameters: Parameters containing workspace_id, storage_name, and file_path
            
        Returns:
            str: Current directory
        """
        return glob.glob(os.path.join(os.getcwd(), '*'), recursive=True)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="create_naas_storage",
                description="Create a new storage in a Naas workspace",
                func=lambda **kwargs: self.create_storage(CreateNaasStorageParameters(**kwargs)),
                args_schema=CreateNaasStorageParameters
            ),
            StructuredTool(
                name="list_naas_storage",
                description="List storage names in a Naas workspace",
                func=lambda **kwargs: self.list_storage(ListNaasStorageParameters(**kwargs)),
                args_schema=ListNaasStorageParameters
            ),
            StructuredTool(
                name="list_naas_storage_files",
                description="List files in a Naas storage location",
                func=lambda **kwargs: self.list_files_from_naas_storage(ListNaasStorageFilesParameters(**kwargs)),
                args_schema=ListNaasStorageFilesParameters
            ),
            StructuredTool(
                name="download_file_from_naas_storage_to_local",
                description="Download a file from Naas storage to local",
                func=lambda **kwargs: self.download_file_to_local(DownloadNaasStorageFileParameters(**kwargs)),
                args_schema=DownloadNaasStorageFileParameters
            ),
            StructuredTool(
                name="download_all_files_from_naas_storage_to_local",
                description="Download all files from a Naas storage location to local",
                func=lambda **kwargs: self.download_all_files_from_naas_storage(DownloadAllFilesFromNaasStorageParameters(**kwargs)),
                args_schema=DownloadAllFilesFromNaasStorageParameters
            ),
            StructuredTool(
                name="upload_naas_storage_file_from_local",
                description="Upload a file to Naas storage from local",
                func=lambda **kwargs: self.upload_file_from_local(UploadNaasStorageFileParameters(**kwargs)),
                args_schema=UploadNaasStorageFileParameters
            ),
            StructuredTool(
                name="upload_all_files_from_local_directory",
                description="Upload all files from a local directory to Naas storage",
                func=lambda **kwargs: self.upload_all_files_from_local_directory(UploadAllFilesFromLocalDirectoryParameters(**kwargs)),
                args_schema=UploadAllFilesFromLocalDirectoryParameters
            ),
            StructuredTool(
                name="get_current_directory",
                description="Get the current directory",
                func=lambda **kwargs: self.get_current_directory(GetCurrentDirectoryParameters(**kwargs)),
                args_schema=GetCurrentDirectoryParameters
            ),
            StructuredTool(
                name="list_files_in_current_directory",
                description="List files in the current directory",
                func=lambda **kwargs: self.list_files_in_current_directory(ListFilesInCurrentDirectoryParameters(**kwargs)),
                args_schema=ListFilesInCurrentDirectoryParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/list_storage_files")
        def list_storage_files(parameters: ListNaasStorageFilesParameters):
            return self.run(parameters)

        @router.post("/download_file")
        def download_file(parameters: DownloadNaasStorageFileParameters):
            content = self.download_file(parameters)
            return StreamingResponse(content, media_type="application/octet-stream")

        @router.post("/upload_file")
        async def upload_file(
            workspace_id: str,
            storage_name: str,
            file_path: str,
            file: UploadFile
        ):
            content = await file.read()
            params = UploadNaasStorageFileParameters(
                workspace_id=workspace_id,
                storage_name=storage_name,
                file_path=file_path,
                content=content
            )
            return self.upload_file(params)