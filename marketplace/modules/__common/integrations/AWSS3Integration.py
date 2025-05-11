from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
import os

LOGO_URL = "https://logo.clearbit.com/amazonaws.com"


@dataclass
class AWSS3IntegrationConfiguration(IntegrationConfiguration):
    """Configuration for AWS S3 integration.

    Attributes:
        aws_access_key_id (str): AWS access key ID
        aws_secret_access_key (str): AWS secret access key
        session_token (str): AWS session token
        region_name (str): AWS region name
    """

    aws_access_key_id: str
    aws_secret_access_key: str
    session_token: str
    region_name: str


class AWSS3Integration(Integration):
    """AWS S3 integration client.

    This integration provides methods to interact with AWS S3's API endpoints.
    """

    __configuration: AWSS3IntegrationConfiguration

    def __init__(self, configuration: AWSS3IntegrationConfiguration):
        """Initialize S3 client with AWS credentials."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.__client = boto3.client(
            "s3",
            aws_access_key_id=self.__configuration.aws_access_key_id,
            aws_secret_access_key=self.__configuration.aws_secret_access_key,
            aws_session_token=self.__configuration.session_token,
            region_name=self.__configuration.region_name,
        )

    def list_buckets(self) -> List[Dict]:
        """List all S3 buckets.

        Returns:
            List[Dict]: List of bucket information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            response = self.__client.list_buckets()
            return [
                {
                    "name": bucket["Name"],
                    "creation_date": bucket["CreationDate"].isoformat(),
                }
                for bucket in response["Buckets"]
            ]
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def list_objects(
        self, bucket: str, prefix: Optional[str] = None, max_keys: int = 1000
    ) -> List[Dict]:
        """List objects in an S3 bucket.

        Args:
            bucket (str): Bucket name
            prefix (str, optional): Filter objects by prefix
            max_keys (int, optional): Maximum number of keys to return

        Returns:
            List[Dict]: List of object information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            objects = []
            is_truncated = True
            continuation_token = None

            while is_truncated:
                params = {"Bucket": bucket, "MaxKeys": max_keys}
                if prefix:
                    params["Prefix"] = prefix
                if continuation_token:
                    params["ContinuationToken"] = continuation_token

                response = self.__client.list_objects_v2(**params)

                if "Contents" in response:
                    for obj in response["Contents"]:
                        objects.append(
                            {
                                "key": obj["Key"],
                                "size": obj["Size"],
                                "last_modified": obj["LastModified"].isoformat(),
                                "etag": obj["ETag"].strip('"'),
                                "storage_class": obj["StorageClass"],
                            }
                        )

                is_truncated = response.get("IsTruncated", False)
                continuation_token = response.get("NextContinuationToken")

            return objects
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def upload_file(
        self,
        source_path: str,
        bucket: str,
        prefix: str,
        destination_path: str,
    ) -> Dict:
        """Upload a file to S3.

        Args:
            source_path (str): Source file path
            bucket (str): Bucket name
            prefix (str): Prefix to add to the key
            destination_path (str): Destination file path or key

        Returns:
            Dict: Upload result

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        key = os.path.join(prefix, destination_path)
        try:
            self.__client.upload_file(source_path, bucket, key)
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def download_file(self, bucket: str, key: str, local_path: str) -> Dict:
        """Download a file from S3.

        Args:
            bucket (str): Bucket name
            key (str): Object key
            local_path (str): Destination file path

        Returns:
            Dict: Object information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            self.__client.download_file(bucket, key, local_path)
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def delete_object(self, bucket: str, key: str) -> Dict:
        """Delete an object from S3.

        Args:
            bucket (str): Bucket name
            key (str): Object key

        Returns:
            Dict: Deletion result

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            response = self.__client.delete_object(Bucket=bucket, Key=key)
            return {
                "bucket": bucket,
                "key": key,
                "version_id": response.get("VersionId"),
                "delete_marker": response.get("DeleteMarker", False),
            }
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expiration: int = 3600,
        operation: str = "get_object",
    ) -> str:
        """Generate a presigned URL for an S3 object.

        Args:
            bucket (str): Bucket name
            key (str): Object key
            expiration (int, optional): URL expiration time in seconds
            operation (str, optional): S3 operation to allow

        Returns:
            str: Presigned URL

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            return self.__client.generate_presigned_url(
                ClientMethod=operation,
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expiration,
            )
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")


def as_tools(configuration: AWSS3IntegrationConfiguration):
    """Convert AWS S3 integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = AWSS3Integration(configuration)

    class ListObjectsSchema(BaseModel):
        bucket: str = Field(..., description="Bucket name")
        prefix: Optional[str] = Field(None, description="Filter objects by prefix")
        max_keys: int = Field(
            default=1000, description="Maximum number of keys to return"
        )

    class UploadFileSchema(BaseModel):
        source_path: str = Field(..., description="Source file path")
        bucket: str = Field(..., description="Bucket name")
        prefix: str = Field(..., description="Prefix to add to the key")
        destination_path: str = Field(..., description="Destination file path or key")

    class DownloadFileSchema(BaseModel):
        bucket: str = Field(..., description="Bucket name")
        key: str = Field(..., description="Object key")
        local_path: str = Field(..., description="Destination file path")

    class ObjectSchema(BaseModel):
        bucket: str = Field(..., description="Bucket name")
        key: str = Field(..., description="Object key")

    class PresignedUrlSchema(BaseModel):
        bucket: str = Field(..., description="Bucket name")
        key: str = Field(..., description="Object key")
        expiration: int = Field(
            default=3600, description="URL expiration time in seconds"
        )
        operation: str = Field(
            default="get_object", description="S3 operation to allow"
        )

    return [
        StructuredTool(
            name="awss3_list_buckets",
            description="List all S3 buckets",
            func=lambda: integration.list_buckets(),
            args_schema=BaseModel,
        ),
        StructuredTool(
            name="awss3_list_objects",
            description="List objects in an S3 bucket",
            func=lambda bucket, prefix, max_keys: integration.list_objects(
                bucket, prefix, max_keys
            ),
            args_schema=ListObjectsSchema,
        ),
        StructuredTool(
            name="awss3_upload_file",
            description="Upload a file to S3",
            func=lambda source_path,
            bucket,
            prefix,
            destination_path: integration.upload_file(
                source_path, bucket, prefix, destination_path
            ),
            args_schema=UploadFileSchema,
        ),
        StructuredTool(
            name="awss3_download_file",
            description="Download a file from S3",
            func=lambda bucket, key, local_path: integration.download_file(
                bucket, key, local_path
            ),
            args_schema=DownloadFileSchema,
        ),
        StructuredTool(
            name="awss3_delete_object",
            description="Delete an object from S3",
            func=lambda bucket, key: integration.delete_object(bucket, key),
            args_schema=ObjectSchema,
        ),
        StructuredTool(
            name="awss3_get_presigned_url",
            description="Generate a presigned URL for an S3 object",
            func=lambda bucket,
            key,
            expiration,
            operation: integration.generate_presigned_url(
                bucket, key, expiration, operation
            ),
            args_schema=PresignedUrlSchema,
        ),
    ]
