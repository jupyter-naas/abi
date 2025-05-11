from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, BinaryIO
from google.oauth2 import service_account
from google.cloud import storage

LOGO_URL = (
    "https://k21academy.com/wp-content/uploads/2021/02/Google-Cloud-Storage-logo.png"
)


@dataclass
class GCPStorageIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for GCP Storage integration.

    Attributes:
        service_account_path (str): Path to service account JSON file
        project_id (str): GCP project ID
    """

    service_account_path: str
    project_id: str


class GCPStorageIntegration(Integration):
    """GCP Cloud Storage API integration client using service account.

    This integration provides methods to interact with GCP Cloud Storage's API endpoints.
    """

    __configuration: GCPStorageIntegrationConfiguration

    def __init__(self, configuration: GCPStorageIntegrationConfiguration):
        """Initialize Storage client with service account credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        try:
            # Load service account credentials
            self.__credentials = service_account.Credentials.from_service_account_file(
                self.__configuration.service_account_path
            )

            # Initialize client
            self.__client = storage.Client(
                credentials=self.__credentials, project=self.__configuration.project_id
            )
        except Exception:
            pass
            # logger.debug(f"Failed to initialize Storage API client: {str(e)}")

    def list_buckets(self) -> List[Dict]:
        """List storage buckets in the project.

        Returns:
            List[Dict]: List of bucket information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            return [
                {
                    "name": bucket.name,
                    "location": bucket.location,
                    "created": bucket.time_created,
                    "storage_class": bucket.storage_class,
                }
                for bucket in self.__client.list_buckets()
            ]
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Storage operation failed: {str(e)}"
            )

    def get_bucket(self, bucket_name: str) -> Dict:
        """Get bucket information.

        Args:
            bucket_name (str): Name of the bucket

        Returns:
            Dict: Bucket information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            bucket = self.__client.get_bucket(bucket_name)
            return {
                "name": bucket.name,
                "location": bucket.location,
                "created": bucket.time_created,
                "storage_class": bucket.storage_class,
                "lifecycle_rules": bucket.lifecycle_rules,
            }
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Storage operation failed: {str(e)}"
            )

    def list_blobs(self, bucket_name: str, prefix: Optional[str] = None) -> List[Dict]:
        """List blobs in a bucket.

        Args:
            bucket_name (str): Name of the bucket
            prefix (str, optional): Filter results to objects whose names begin with this prefix

        Returns:
            List[Dict]: List of blob information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            blobs = self.__client.list_blobs(bucket_name, prefix=prefix)
            return [
                {
                    "name": blob.name,
                    "size": blob.size,
                    "updated": blob.updated,
                    "content_type": blob.content_type,
                    "md5_hash": blob.md5_hash,
                }
                for blob in blobs
            ]
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Storage operation failed: {str(e)}"
            )

    def upload_blob(
        self,
        bucket_name: str,
        source_file: Union[str, BinaryIO],
        destination_blob_name: str,
    ) -> Dict:
        """Upload a file to Cloud Storage.

        Args:
            bucket_name (str): Name of the bucket
            source_file (Union[str, BinaryIO]): Source file path or file-like object
            destination_blob_name (str): Destination blob name

        Returns:
            Dict: Upload result

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            bucket = self.__client.bucket(bucket_name)
            blob = bucket.blob(destination_blob_name)

            if isinstance(source_file, str):
                blob.upload_from_filename(source_file)
            else:
                blob.upload_from_file(source_file)

            return {
                "name": blob.name,
                "bucket": bucket_name,
                "size": blob.size,
                "updated": blob.updated,
                "md5_hash": blob.md5_hash,
            }
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Storage operation failed: {str(e)}"
            )

    def download_blob(
        self,
        bucket_name: str,
        source_blob_name: str,
        destination_file: Union[str, BinaryIO],
    ) -> Dict:
        """Download a blob from Cloud Storage.

        Args:
            bucket_name (str): Name of the bucket
            source_blob_name (str): Source blob name
            destination_file (Union[str, BinaryIO]): Destination file path or file-like object

        Returns:
            Dict: Download result

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            bucket = self.__client.bucket(bucket_name)
            blob = bucket.blob(source_blob_name)

            if isinstance(destination_file, str):
                blob.download_to_filename(destination_file)
            else:
                blob.download_to_file(destination_file)

            return {
                "name": blob.name,
                "bucket": bucket_name,
                "size": blob.size,
                "updated": blob.updated,
                "md5_hash": blob.md5_hash,
            }
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Storage operation failed: {str(e)}"
            )


def as_tools(configuration: GCPStorageIntegrationConfiguration):
    """Convert GCP Storage integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GCPStorageIntegration(configuration)

    class BucketSchema(BaseModel):
        bucket_name: str = Field(..., description="Name of the bucket")

    class ListBlobsSchema(BaseModel):
        bucket_name: str = Field(..., description="Name of the bucket")
        prefix: Optional[str] = Field(
            None,
            description="Filter results to objects whose names begin with this prefix",
        )

    class UploadBlobSchema(BaseModel):
        bucket_name: str = Field(..., description="Name of the bucket")
        source_file: str = Field(..., description="Source file path")
        destination_blob_name: str = Field(..., description="Destination blob name")

    class DownloadBlobSchema(BaseModel):
        bucket_name: str = Field(..., description="Name of the bucket")
        source_blob_name: str = Field(..., description="Source blob name")
        destination_file: str = Field(..., description="Destination file path")

    return [
        StructuredTool(
            name="gcpstorage_list_buckets",
            description="List Cloud Storage buckets",
            func=lambda: integration.list_buckets(),
            args_schema=BaseModel,
        ),
        StructuredTool(
            name="gcpstorage_get_bucket",
            description="Get bucket information",
            func=lambda bucket_name: integration.get_bucket(bucket_name),
            args_schema=BucketSchema,
        ),
        StructuredTool(
            name="gcpstorage_list_blobs",
            description="List blobs in a bucket",
            func=lambda bucket_name, prefix: integration.list_blobs(
                bucket_name, prefix
            ),
            args_schema=ListBlobsSchema,
        ),
        StructuredTool(
            name="gcpstorage_upload_blob",
            description="Upload a file to Cloud Storage",
            func=lambda bucket_name,
            source_file,
            destination_blob_name: integration.upload_blob(
                bucket_name, source_file, destination_blob_name
            ),
            args_schema=UploadBlobSchema,
        ),
        StructuredTool(
            name="gcpstorage_download_blob",
            description="Download a blob from Cloud Storage",
            func=lambda bucket_name,
            source_blob_name,
            destination_file: integration.download_blob(
                bucket_name, source_blob_name, destination_file
            ),
            args_schema=DownloadBlobSchema,
        ),
    ]
