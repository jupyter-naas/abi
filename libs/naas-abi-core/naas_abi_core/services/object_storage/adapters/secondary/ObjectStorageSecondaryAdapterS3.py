from queue import Queue
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
)


class ObjectStorageSecondaryAdapterS3(IObjectStorageAdapter):
    """S3 implementation of the Object Storage adapter using boto3."""

    def __init__(
        self,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        base_prefix: str = "",
        session_token: str | None = None,
        endpoint_url: str | None = None,
    ):
        """Initialize S3 adapter with bucket name and credentials.

        Args:
            bucket_name (str): Name of the S3 bucket to use
            access_key_id (str): AWS access key ID
            secret_access_key (str): AWS secret access key
            base_prefix (str, optional): Base prefix to prepend to all operations. Defaults to ""
            session_token (str, optional): AWS session token. Defaults to None
        """
        self.bucket_name = bucket_name
        self.base_prefix = base_prefix.rstrip("/")  # Remove trailing slash if present

        args = {
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "aws_session_token": session_token,
        }

        if endpoint_url:
            args["endpoint_url"] = endpoint_url

        self.s3_client = boto3.client("s3", **args)

    def __get_full_key(self, prefix: str, key: str | None = None) -> str:
        """Construct full key path including base prefix.

        Args:
            prefix (str): Prefix/folder path
            key (str, optional): Object key name

        Returns:
            str: Full key path
        """
        # if key is None:
        #     return f"{self.base_prefix}/{prefix}".lstrip('/')
        return f"{self.base_prefix + '/' if self.base_prefix else ''}{prefix + '/' if prefix else ''}{key if key else ''}".lstrip(
            "/"
        )

    def __object_exists(self, prefix: str, key: str | None = None) -> bool:
        """Check if an object exists in S3.

        Args:
            prefix (str): Prefix/folder path
            key (str, optional): Object key name

        Returns:
            bool: True if exists, raises exception if not
        """
        try:
            if key is None:
                # Check if prefix exists by listing objects
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=self.__get_full_key(prefix),
                    MaxKeys=1,
                )
                if "Contents" not in response:
                    raise Exceptions.ObjectNotFound(f"Prefix {prefix} not found")
            else:
                # Check specific object
                self.s3_client.head_object(
                    Bucket=self.bucket_name, Key=self.__get_full_key(prefix, key)
                )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ["404", "NoSuchKey"]:
                raise Exceptions.ObjectNotFound(f"Object {prefix}/{key} not found")
            raise e

    def get_object(self, prefix: str, key: str) -> bytes:
        """Get object from S3 bucket.

        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name

        Returns:
            bytes: Object content
        """
        self.__object_exists(prefix, key)

        response = self.s3_client.get_object(
            Bucket=self.bucket_name, Key=self.__get_full_key(prefix, key)
        )
        return response["Body"].read()

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        """Put object into S3 bucket.

        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name
            content (bytes): Content to upload
        """
        self.s3_client.put_object(
            Bucket=self.bucket_name, Key=self.__get_full_key(prefix, key), Body=content
        )

    def delete_object(self, prefix: str, key: str) -> None:
        """Delete object from S3 bucket.

        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name
        """
        self.__object_exists(prefix, key)

        self.s3_client.delete_object(
            Bucket=self.bucket_name, Key=self.__get_full_key(prefix, key)
        )

    def list_objects(self, prefix: str, queue: Optional[Queue] = None) -> list[str]:
        """List objects in S3 bucket with given prefix.

        Args:
            prefix (str): Prefix/folder path to list

        Returns:
            list[str]: List of object keys at depth 1 only (direct children)
        """
        self.__object_exists(prefix)

        objects = []
        paginator = self.s3_client.get_paginator("list_objects_v2")

        for page in paginator.paginate(
            Bucket=self.bucket_name,
            Prefix=self.__get_full_key(prefix),
            Delimiter="/",  # This makes it list only one level deep
        ):
            # Get regular objects at this level
            if "Contents" in page:
                for obj in page["Contents"]:
                    # Remove base prefix from returned keys
                    key = obj["Key"]
                    if self.base_prefix:
                        key = key.replace(f"{self.base_prefix}/", "", 1)
                    if key != "":
                        objects.append(key)
                        if queue:
                            queue.put(key)

            # Get subfolders at this level
            if "CommonPrefixes" in page:
                for prefix_obj in page["CommonPrefixes"]:
                    prefix_key = prefix_obj["Prefix"]
                    if self.base_prefix:
                        prefix_key = prefix_key.replace(f"{self.base_prefix}/", "", 1)
                    if prefix_key != "":
                        objects.append(prefix_key)
                        if queue:
                            queue.put(prefix_key)
        return objects
