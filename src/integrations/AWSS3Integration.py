from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, BinaryIO
import boto3
from botocore.exceptions import ClientError

@dataclass
class AWSS3IntegrationConfiguration(IntegrationConfiguration):
    """Configuration for AWS S3 integration.
    
    Attributes:
        aws_access_key_id (str): AWS access key ID
        aws_secret_access_key (str): AWS secret access key
        region_name (str): AWS region name
    """
    aws_access_key_id: str
    aws_secret_access_key: str
    region_name: str

class AWSS3Integration(Integration):
    """AWS S3 integration client."""

    __configuration: AWSS3IntegrationConfiguration
    __client: boto3.client

    def __init__(self, configuration: AWSS3IntegrationConfiguration):
        """Initialize S3 client with AWS credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.__client = boto3.client(
            's3',
            aws_access_key_id=self.__configuration.aws_access_key_id,
            aws_secret_access_key=self.__configuration.aws_secret_access_key,
            region_name=self.__configuration.region_name
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
            return [{
                'name': bucket['Name'],
                'creation_date': bucket['CreationDate'].isoformat()
            } for bucket in response['Buckets']]
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def list_objects(self,
                    bucket: str,
                    prefix: Optional[str] = None,
                    max_keys: int = 1000) -> List[Dict]:
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
            params = {
                'Bucket': bucket,
                'MaxKeys': max_keys
            }
            if prefix:
                params['Prefix'] = prefix

            response = self.__client.list_objects_v2(**params)
            
            objects = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'etag': obj['ETag'].strip('"'),
                        'storage_class': obj['StorageClass']
                    })
            return objects
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def upload_file(self,
                   bucket: str,
                   key: str,
                   file: Union[str, BinaryIO],
                   content_type: Optional[str] = None) -> Dict:
        """Upload a file to S3.
        
        Args:
            bucket (str): Bucket name
            key (str): Object key
            file (Union[str, BinaryIO]): File path or file-like object
            content_type (str, optional): Content type of the file
            
        Returns:
            Dict: Upload result
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type

            if isinstance(file, str):
                self.__client.upload_file(file, bucket, key, ExtraArgs=extra_args)
            else:
                self.__client.upload_fileobj(file, bucket, key, ExtraArgs=extra_args)

            response = self.__client.head_object(Bucket=bucket, Key=key)
            return {
                'bucket': bucket,
                'key': key,
                'size': response['ContentLength'],
                'etag': response['ETag'].strip('"'),
                'last_modified': response['LastModified'].isoformat(),
                'content_type': response.get('ContentType')
            }
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def download_file(self,
                     bucket: str,
                     key: str,
                     file: Union[str, BinaryIO]) -> Dict:
        """Download a file from S3.
        
        Args:
            bucket (str): Bucket name
            key (str): Object key
            file (Union[str, BinaryIO]): Destination file path or file-like object
            
        Returns:
            Dict: Object information
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            if isinstance(file, str):
                self.__client.download_file(bucket, key, file)
            else:
                self.__client.download_fileobj(bucket, key, file)

            response = self.__client.head_object(Bucket=bucket, Key=key)
            return {
                'bucket': bucket,
                'key': key,
                'size': response['ContentLength'],
                'etag': response['ETag'].strip('"'),
                'last_modified': response['LastModified'].isoformat(),
                'content_type': response.get('ContentType')
            }
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
                'bucket': bucket,
                'key': key,
                'version_id': response.get('VersionId'),
                'delete_marker': response.get('DeleteMarker', False)
            }
        except ClientError as e:
            raise IntegrationConnectionError(f"S3 operation failed: {str(e)}")

    def generate_presigned_url(self,
                             bucket: str,
                             key: str,
                             expiration: int = 3600,
                             operation: str = 'get_object') -> str:
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
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
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
        max_keys: int = Field(default=1000, description="Maximum number of keys to return")

    class UploadFileSchema(BaseModel):
        bucket: str = Field(..., description="Bucket name")
        key: str = Field(..., description="Object key")
        file: str = Field(..., description="File path")
        content_type: Optional[str] = Field(None, description="Content type of the file")

    class DownloadFileSchema(BaseModel):
        bucket: str = Field(..., description="Bucket name")
        key: str = Field(..., description="Object key")
        file: str = Field(..., description="Destination file path")

    class ObjectSchema(BaseModel):
        bucket: str = Field(..., description="Bucket name")
        key: str = Field(..., description="Object key")

    class PresignedUrlSchema(BaseModel):
        bucket: str = Field(..., description="Bucket name")
        key: str = Field(..., description="Object key")
        expiration: int = Field(default=3600, description="URL expiration time in seconds")
        operation: str = Field(default='get_object', description="S3 operation to allow")
    
    return [
        StructuredTool(
            name="list_s3_buckets",
            description="List all S3 buckets",
            func=lambda: integration.list_buckets(),
            args_schema=BaseModel
        ),
        StructuredTool(
            name="list_s3_objects",
            description="List objects in an S3 bucket",
            func=lambda bucket, prefix, max_keys: integration.list_objects(bucket, prefix, max_keys),
            args_schema=ListObjectsSchema
        ),
        StructuredTool(
            name="upload_to_s3",
            description="Upload a file to S3",
            func=lambda bucket, key, file, content_type:
                integration.upload_file(bucket, key, file, content_type),
            args_schema=UploadFileSchema
        ),
        StructuredTool(
            name="download_from_s3",
            description="Download a file from S3",
            func=lambda bucket, key, file: integration.download_file(bucket, key, file),
            args_schema=DownloadFileSchema
        ),
        StructuredTool(
            name="delete_from_s3",
            description="Delete an object from S3",
            func=lambda bucket, key: integration.delete_object(bucket, key),
            args_schema=ObjectSchema
        ),
        StructuredTool(
            name="get_s3_presigned_url",
            description="Generate a presigned URL for an S3 object",
            func=lambda bucket, key, expiration, operation:
                integration.generate_presigned_url(bucket, key, expiration, operation),
            args_schema=PresignedUrlSchema
        )
    ] 