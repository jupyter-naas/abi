from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, BinaryIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
import io

@dataclass
class GoogleDriveIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Google Drive integration.
    
    Attributes:
        service_account_path (str): Path to service account JSON file
        subject_email (str): Email of the user to impersonate
        scopes (List[str]): List of required API scopes
    """
    service_account_path: str
    subject_email: str
    scopes: List[str] = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = [
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/drive.file'
            ]

class GoogleDriveIntegration(Integration):
    """Google Drive API integration client using service account.
    
    This class provides methods to interact with Google Drive's API endpoints
    for file and folder operations.
    """

    __configuration: GoogleDriveIntegrationConfiguration
    __service: any  # Drive API service

    def __init__(self, configuration: GoogleDriveIntegrationConfiguration):
        """Initialize Drive client with service account credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        # Load service account credentials
        credentials = service_account.Credentials.from_service_account_file(
            self.__configuration.service_account_path,
            scopes=self.__configuration.scopes
        )
        
        # Create delegated credentials for impersonation
        delegated_credentials = credentials.with_subject(self.__configuration.subject_email)
        
        # Build the service
        self.__service = build('drive', 'v3', credentials=delegated_credentials)

    def list_files(self, 
                  query: Optional[str] = None,
                  page_size: int = 100,
                  fields: str = "files(id, name, mimeType, createdTime, modifiedTime)") -> List[Dict]:
        """List files and folders in Drive.
        
        Args:
            query (str, optional): Search query (Drive query syntax)
            page_size (int, optional): Maximum number of files to return
            fields (str, optional): Fields to include in the response
            
        Returns:
            List[Dict]: List of files and folders
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            results = []
            page_token = None
            
            while True:
                response = self.__service.files().list(
                    q=query,
                    pageSize=page_size,
                    fields=f"nextPageToken, {fields}",
                    pageToken=page_token
                ).execute()
                
                results.extend(response.get('files', []))
                page_token = response.get('nextPageToken')
                
                if not page_token:
                    break
                    
            return results
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Drive API request failed: {str(e)}")

    def get_file(self, file_id: str, fields: str = "id, name, mimeType, createdTime, modifiedTime") -> Dict:
        """Get file metadata.
        
        Args:
            file_id (str): File ID
            fields (str, optional): Fields to include in the response
            
        Returns:
            Dict: File metadata
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            return self.__service.files().get(
                fileId=file_id,
                fields=fields
            ).execute()
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Drive API request failed: {str(e)}")

    def create_folder(self, 
                     name: str, 
                     parent_id: Optional[str] = None) -> Dict:
        """Create a new folder.
        
        Args:
            name (str): Folder name
            parent_id (str, optional): Parent folder ID
            
        Returns:
            Dict: Created folder metadata
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            return self.__service.files().create(
                body=file_metadata,
                fields='id, name, mimeType'
            ).execute()
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Drive API request failed: {str(e)}")

    def upload_file(self,
                   name: str,
                   content: Union[str, bytes, BinaryIO],
                   mime_type: str,
                   parent_id: Optional[str] = None) -> Dict:
        """Upload a file.
        
        Args:
            name (str): File name
            content (Union[str, bytes, BinaryIO]): File content
            mime_type (str): File MIME type
            parent_id (str, optional): Parent folder ID
            
        Returns:
            Dict: Uploaded file metadata
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            file_metadata = {'name': name}
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            if isinstance(content, (str, bytes)):
                if isinstance(content, str):
                    content = content.encode('utf-8')
                media = MediaIoBaseUpload(
                    io.BytesIO(content),
                    mimetype=mime_type,
                    resumable=True
                )
            else:
                media = MediaIoBaseUpload(
                    content,
                    mimetype=mime_type,
                    resumable=True
                )
                
            return self.__service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType'
            ).execute()
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Drive API request failed: {str(e)}")

    def download_file(self, file_id: str) -> bytes:
        """Download a file's content.
        
        Args:
            file_id (str): File ID
            
        Returns:
            bytes: File content
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            request = self.__service.files().get_media(fileId=file_id)
            file_content = request.execute()
            return file_content
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Drive API request failed: {str(e)}")

    def delete_file(self, file_id: str) -> None:
        """Delete a file or folder.
        
        Args:
            file_id (str): File or folder ID
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            self.__service.files().delete(fileId=file_id).execute()
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Drive API request failed: {str(e)}")

def as_tools(configuration: GoogleDriveIntegrationConfiguration):
    """Convert Google Drive integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = GoogleDriveIntegration(configuration)
    
    class ListFilesSchema(BaseModel):
        query: Optional[str] = Field(None, description="Search query (Drive query syntax)")
        page_size: int = Field(default=100, description="Maximum number of files to return")
        fields: str = Field(
            default="files(id, name, mimeType, createdTime, modifiedTime)",
            description="Fields to include in the response"
        )

    class FileSchema(BaseModel):
        file_id: str = Field(..., description="File ID")
        fields: str = Field(
            default="id, name, mimeType, createdTime, modifiedTime",
            description="Fields to include in the response"
        )

    class CreateFolderSchema(BaseModel):
        name: str = Field(..., description="Folder name")
        parent_id: Optional[str] = Field(None, description="Parent folder ID")

    class UploadFileSchema(BaseModel):
        name: str = Field(..., description="File name")
        content: Union[str, bytes] = Field(..., description="File content")
        mime_type: str = Field(..., description="File MIME type")
        parent_id: Optional[str] = Field(None, description="Parent folder ID")
    
    return [
        StructuredTool(
            name="list_drive_files",
            description="List files and folders in Google Drive",
            func=lambda query, page_size, fields: integration.list_files(query, page_size, fields),
            args_schema=ListFilesSchema
        ),
        StructuredTool(
            name="get_drive_file",
            description="Get file metadata from Google Drive",
            func=lambda file_id, fields: integration.get_file(file_id, fields),
            args_schema=FileSchema
        ),
        StructuredTool(
            name="create_drive_folder",
            description="Create a new folder in Google Drive",
            func=lambda name, parent_id: integration.create_folder(name, parent_id),
            args_schema=CreateFolderSchema
        ),
        StructuredTool(
            name="upload_drive_file",
            description="Upload a file to Google Drive",
            func=lambda name, content, mime_type, parent_id: integration.upload_file(
                name, content, mime_type, parent_id
            ),
            args_schema=UploadFileSchema
        ),
        StructuredTool(
            name="download_drive_file",
            description="Download a file's content from Google Drive",
            func=lambda file_id: integration.download_file(file_id),
            args_schema=FileSchema
        ),
        StructuredTool(
            name="delete_drive_file",
            description="Delete a file or folder from Google Drive",
            func=lambda file_id: integration.delete_file(file_id),
            args_schema=FileSchema
        )
    ] 