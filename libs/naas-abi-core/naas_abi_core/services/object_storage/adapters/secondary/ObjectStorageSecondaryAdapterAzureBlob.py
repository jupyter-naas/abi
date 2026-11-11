import io
from collections.abc import Iterator
from contextlib import contextmanager
from queue import Queue
from typing import Any, BinaryIO

from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
    ObjectMetaData,
)

try:
    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import (
        BlobPrefix,
        BlobProperties,
        ContainerClient,
        StorageErrorCode,
        StorageStreamDownloader,
    )
except ModuleNotFoundError as error:
    if (error.name or "").split(".")[0] != "azure":
        raise
    raise ModuleNotFoundError(
        "The Azure Blob Storage object storage adapter needs the `azure` extra "
        "of naas-abi-core, which is not installed: uv add 'naas-abi-core[azure]' "
        "(or pip install 'naas-abi-core[azure]').",
        name=error.name,
    ) from error


# Metadata Azure sets on a directory of a hierarchical-namespace (Data Lake
# Storage Gen2) account, which the Blob API lists like a zero-byte blob.
_DIRECTORY_METADATA_KEY = "hdi_isfolder"


class ObjectStorageSecondaryAdapterAzureBlob(IObjectStorageAdapter):
    """Azure Blob Storage implementation of the Object Storage adapter.

    Authenticates with Microsoft Entra ID through ``DefaultAzureCredential``
    (managed identity, workload identity, environment, Azure CLI login): no
    account key or SAS is needed, only a data-plane role on the container such
    as *Storage Blob Data Contributor*. ``connection_string`` is the explicit
    alternative for stores reached without Entra ID, such as the Azurite
    emulator.

    Blob names follow the S3 adapter's layout: ``<base_prefix>/<prefix>/<key>``,
    with ``/`` as the virtual directory delimiter.
    """

    def __init__(
        self,
        container_name: str,
        account_url: str | None = None,
        base_prefix: str = "",
        managed_identity_client_id: str | None = None,
        connection_string: str | None = None,
    ):
        """Initialize the adapter. No request is made until the first operation.

        Args:
            container_name (str): Name of the blob container to use.
            account_url (str, optional): Blob service endpoint of the storage
                account, e.g. ``https://<account>.blob.core.windows.net``. Used
                as given, so a private endpoint or a sovereign cloud endpoint
                works. Required unless ``connection_string`` is set.
            base_prefix (str, optional): Prefix prepended to every blob name.
                Defaults to "".
            managed_identity_client_id (str, optional): Client ID of the
                user-assigned managed identity to authenticate as. Defaults to
                ``AZURE_CLIENT_ID`` when set, else the system-assigned identity.
            connection_string (str, optional): Storage connection string, in
                place of ``account_url`` and Entra ID (account key or SAS).
        """
        if bool(account_url) == bool(connection_string):
            raise ValueError(
                "Azure Blob object storage needs exactly one of account_url "
                "(Entra ID) or connection_string."
            )
        if connection_string and managed_identity_client_id:
            raise ValueError(
                "managed_identity_client_id applies to account_url (Entra ID), "
                "not to connection_string."
            )

        self.container_name = container_name
        self.base_prefix = self.__normalize_key_part(base_prefix)

        if connection_string:
            self.container_client = ContainerClient.from_connection_string(
                connection_string, container_name
            )
        else:
            assert account_url is not None
            credential_kwargs: dict[str, Any] = {}
            # Only when set: an explicit None makes DefaultAzureCredential
            # ignore AZURE_CLIENT_ID and use the system-assigned identity.
            if managed_identity_client_id:
                credential_kwargs["managed_identity_client_id"] = (
                    managed_identity_client_id
                )
            self.container_client = ContainerClient(
                account_url=account_url,
                container_name=container_name,
                credential=DefaultAzureCredential(**credential_kwargs),
            )

    @staticmethod
    def __normalize_key_part(value: str | None) -> str:
        if not value:
            return ""
        return "/".join(part for part in value.split("/") if part)

    def __get_full_key(self, prefix: str, key: str | None = None) -> str:
        """Blob name for *prefix/key*; with no key, the listing prefix of
        *prefix*, ending in ``/`` unless it is the container root."""
        parts = [
            part
            for part in [
                self.base_prefix,
                self.__normalize_key_part(prefix),
                self.__normalize_key_part(key),
            ]
            if part
        ]
        full_key = "/".join(parts)
        if key is None and full_key:
            return f"{full_key}/"
        return full_key

    def __relative(self, name: str) -> str:
        """A listed blob name without the base prefix."""
        if self.base_prefix:
            return name.removeprefix(f"{self.base_prefix}/")
        return name

    @staticmethod
    def __is_directory(blob: BlobProperties) -> bool:
        """A folder placeholder, not an object: a name ending in ``/``, or a
        hierarchical-namespace directory."""
        if blob.name.endswith("/"):
            return True
        metadata = blob.metadata or {}
        return str(metadata.get(_DIRECTORY_METADATA_KEY, "")).lower() == "true"

    @staticmethod
    def __not_found(error: ResourceNotFoundError, prefix: str, key: str) -> Exception:
        """``ObjectNotFound`` for a missing blob. A missing container is a
        configuration error, raised as is."""
        if getattr(error, "error_code", None) == StorageErrorCode.CONTAINER_NOT_FOUND:
            return error
        return Exceptions.ObjectNotFound(f"Object {prefix}/{key} not found")

    def __download(self, prefix: str, key: str) -> StorageStreamDownloader[bytes]:
        try:
            return self.container_client.download_blob(self.__get_full_key(prefix, key))
        except ResourceNotFoundError as error:
            raise self.__not_found(error, prefix, key) from error

    def get_object(self, prefix: str, key: str) -> bytes:
        """Get object content.

        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name

        Returns:
            bytes: Object content
        """
        return self.__download(prefix, key).readall()

    @contextmanager
    def get_object_stream(self, prefix: str, key: str) -> Iterator[BinaryIO]:
        """Stream the blob in bounded chunks instead of buffering it whole.

        The download is opened before the body runs, so a missing blob raises
        ``ObjectNotFound`` here. The SDK then fetches the rest chunk by chunk
        as the caller reads.
        """
        downloader = self.__download(prefix, key)
        with io.BufferedReader(_BlobReader(downloader)) as stream:
            yield stream

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        """Put object, replacing any blob of the same name.

        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name
            content (bytes): Content to upload
        """
        self.container_client.upload_blob(
            self.__get_full_key(prefix, key), content, overwrite=True
        )

    def put_object_stream(self, prefix: str, key: str, stream: BinaryIO) -> None:
        """Upload from ``stream`` in blocks, without reading it whole."""
        self.container_client.upload_blob(
            self.__get_full_key(prefix, key), stream, overwrite=True
        )

    def delete_object(self, prefix: str, key: str) -> None:
        """Delete object.

        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name
        """
        try:
            self.container_client.delete_blob(self.__get_full_key(prefix, key))
        except ResourceNotFoundError as error:
            raise self.__not_found(error, prefix, key) from error

    def list_objects(self, prefix: str, queue: Queue | None = None) -> list[str]:
        """List the direct children of *prefix*.

        Args:
            prefix (str): Prefix/folder path to list

        Returns:
            list[str]: Object names, and folder names ending in ``/``, one level
                deep, relative to the base prefix.
        """
        objects = []
        for item in self.container_client.walk_blobs(
            name_starts_with=self.__get_full_key(prefix) or None,
            include=["metadata"],
            delimiter="/",
        ):
            if isinstance(item, BlobPrefix):
                name = self.__relative(item.name)
            elif self.__is_directory(item):
                continue
            else:
                name = self.__relative(item.name)
            if name:
                objects.append(name)
                if queue:
                    queue.put(name)
        if not objects:
            raise Exceptions.ObjectNotFound(f"Prefix {prefix} not found")
        return objects

    def list_objects_recursive(
        self, prefix: str, queue: Queue | None = None
    ) -> list[str]:
        """List every object at or beneath *prefix*, at any nesting depth.

        Args:
            prefix (str): Prefix/folder path to walk

        Returns:
            list[str]: Object names relative to the base prefix. A flat listing
                has no folder entries; folder placeholders (a name ending in
                ``/``, a hierarchical-namespace directory) are skipped.
        """
        objects = []
        for blob in self.container_client.list_blobs(
            name_starts_with=self.__get_full_key(prefix) or None,
            include=["metadata"],
        ):
            if self.__is_directory(blob):
                continue
            name = self.__relative(blob.name)
            if name:
                objects.append(name)
                if queue:
                    queue.put(name)
        if not objects:
            raise Exceptions.ObjectNotFound(f"Prefix {prefix} not found")
        return objects

    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        """Get object metadata from the blob's properties.

        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name

        Returns:
            ObjectMetaData: Size, times, content type and encoding, and the
                blob URL as ``file_path``.
        """
        blob_client = self.container_client.get_blob_client(
            self.__get_full_key(prefix, key)
        )
        try:
            properties = blob_client.get_blob_properties()
        except ResourceNotFoundError as error:
            raise self.__not_found(error, prefix, key) from error

        content_settings = properties.content_settings
        return ObjectMetaData(
            file_path=blob_client.url,
            file_name=key.split("/")[-1] if key else "",
            file_size_bytes=properties.size or 0,
            created_time=properties.creation_time,
            modified_time=properties.last_modified,
            accessed_time=properties.last_accessed_on,
            permissions=None,
            mime_type=content_settings.content_type or None,
            encoding=content_settings.content_encoding or None,
        )


class _BlobReader(io.RawIOBase):
    """A readable raw stream over a blob download, for ``io.BufferedReader``."""

    def __init__(self, downloader: StorageStreamDownloader[bytes]):
        super().__init__()
        self._downloader = downloader

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        data = self._downloader.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)
