# Object Storage Service

[Source Code](../../../lib/abi/services/object_storage)


## Overview

The Object Storage Service provides a unified interface for interacting with files and objects across different storage backends. It abstracts away the underlying storage implementation through adapters, allowing seamless switching between different storage solutions.

The service currently supports the following adapters:

- **AWS S3 Adapter**: Uses Boto3 to interact with any S3-compatible storage backend (not limited to AWS)
- **File System Adapter**: Used in local development to interface with the local file system
- **Naas Adapter**: Leverages the S3 adapter but automatically retrieves credentials from your Naas account

This abstraction allows pipelines and other components to work with storage in a consistent way, regardless of whether they're running in development or production environments. The service provides core operations like:

- Getting objects/files
- Putting (uploading) objects/files  
- Deleting objects/files
- Listing objects/files in a directory/prefix

The storage backend used is determined by the environment configuration, defaulting to local filesystem storage in development and using cloud storage in production environments.

## Usage

### Default initialization

The Object Storage Service is typically initialized through the application's service manager. The initialization differs between development and production environments:

```python
from src import services

# Access the storage service
storage = services.storage_service
```

#### Development Environment

In development mode (when `ENV=dev` environment variable is set), the service automatically initializes with the File System adapter and detects the storage location:

```python
# Development initialization (happens automatically)
storage_service = ObjectStorageFactory.ObjectStorageServiceFS__find_storage()
```

You can check the loading of the service in [services.py](../../../src/services.py)

#### Production Environment

In production, the service uses the Naas adapter with credentials from your configuration:

```python
# Production initialization (happens automatically)
storage_service = ObjectStorageFactory.ObjectStorageServiceNaas(
    naas_api_key=secret.get('NAAS_API_KEY'),
    workspace_id=config.workspace_id,
    storage_name=config.storage_name
)
```

This initialization is handled automatically when the application starts, allowing you to use the storage service directly without manual setup.

### Factories

The Object Storage Service provides several factory methods to create storage service instances based on your needs:

```python
from abi.services.object_storage.ObjectStorageFactory import ObjectStorageFactory

# Create a filesystem-based storage service by auto-detecting the storage folder
storage = ObjectStorageFactory.ObjectStorageServiceFS__find_storage()

# Create a filesystem-based storage service with a specific base path
storage = ObjectStorageFactory.ObjectStorageServiceFS("/path/to/storage")

# Create an S3-based storage service
storage = ObjectStorageFactory.ObjectStorageServiceS3(
    access_key_id="YOUR_ACCESS_KEY",
    secret_access_key="YOUR_SECRET_KEY",
    bucket_name="your-bucket-name",
    base_prefix="your/prefix/path"
)

# Create a Naas-based storage service
storage = ObjectStorageFactory.ObjectStorageServiceNaas(
    naas_api_key="YOUR_NAAS_API_KEY",
    workspace_id="your-workspace-id",
    storage_name="your-storage-name",
    base_prefix="your/prefix/path"  # Optional
)
```

Each factory method returns an instance of `ObjectStorageService` that provides a unified interface for file operations regardless of the underlying storage backend.

## API Reference

### `ObjectStorageService`

The main service class implementing the `IObjectStorageDomain` interface. It provides a unified API for interacting with different storage backends through adapters.

#### Methods

##### `get_object(prefix: str, key: str) -> bytes`

Retrieves an object from storage.

- **Parameters**:
  - `prefix`: The directory or folder path where the object is located
  - `key`: The name of the object/file to retrieve
- **Returns**: Binary content of the object as bytes
- **Raises**: `ObjectNotFound` exception if the object does not exist

##### `put_object(prefix: str, key: str, content: bytes) -> None`

Stores an object in the storage system.

- **Parameters**:
  - `prefix`: The directory or folder path where the object should be stored
  - `key`: The name to give the object/file
  - `content`: The binary content to store as bytes
- **Returns**: None

##### `delete_object(prefix: str, key: str) -> None`

Deletes an object from storage.

- **Parameters**:
  - `prefix`: The directory or folder path where the object is located
  - `key`: The name of the object/file to delete
- **Returns**: None
- **Raises**: `ObjectNotFound` exception if the object does not exist

##### `list_objects(prefix: str = '', queue: Optional[Queue] = None) -> list[str]`

Lists objects in a directory/prefix.

- **Parameters**:
  - `prefix`: The directory or folder path to list objects from (defaults to empty string for root)
  - `queue`: Optional Queue object to stream results to as they're found (useful for large directories)
- **Returns**: List of object paths found at the specified prefix
- **Raises**: `ObjectNotFound` exception if the prefix does not exist

### Storage Adapters

The service supports multiple storage backends through adapters:

#### File System Adapter (`ObjectStorageSecondaryAdapterFS`)

Adapter for local file system storage.

- **Initialization**: `ObjectStorageFactory.ObjectStorageServiceFS(base_path: str)`
- **Auto-detection**: `ObjectStorageFactory.ObjectStorageServiceFS__find_storage(needle: str = 'storage')`

#### S3 Adapter (`ObjectStorageSecondaryAdapterS3`)

Adapter for S3-compatible storage.

- **Initialization**: 
  ```python
  ObjectStorageFactory.ObjectStorageServiceS3(
      access_key_id: str, 
      secret_access_key: str, 
      bucket_name: str, 
      base_prefix: str,
      session_token: str = None
  )
  ```

#### Naas Adapter (`ObjectStorageSecondaryAdapterNaas`)

Adapter for using Naas-managed S3 storage with automatic credential management.

- **Initialization**:
  ```python
  ObjectStorageFactory.ObjectStorageServiceNaas(
      naas_api_key: str,
      workspace_id: str,
      storage_name: str,
      base_prefix: str = ""
  )
  ```
  - Automatically refreshes credentials every 20 minutes
  - Credentials are obtained from the Naas API

### Exceptions

All adapters may throw these exceptions when operations fail:

- `ObjectNotFound`: Raised when trying to access an object or prefix that doesn't exist
- `ObjectAlreadyExists`: Raised when trying to create an object that already exists

### Usage Patterns

Objects are addressed using a combination of `prefix` and `key`:
- `prefix`: Works like a directory path
- `key`: The filename within that directory

For example:
```python
# Store a file 'data.json' in the 'users/profiles' directory
storage_service.put_object('users/profiles', 'data.json', json_data_bytes)

# Read that same file
content = storage_service.get_object('users/profiles', 'data.json')

# List all files in the 'users/profiles' directory
files = storage_service.list_objects('users/profiles')

# Delete the file
storage_service.delete_object('users/profiles', 'data.json')
```

When listing objects with `list_objects()`, the returned strings are paths relative to the specified prefix.

## How to create a new secondary adapter

Creating a new secondary adapter allows you to extend the Object Storage Service to work with additional storage backends. Below is a step-by-step guide on how to create an FTP adapter as an example.

### Steps to Create a New Adapter

1. **Create a new adapter class** that implements the `IObjectStorageAdapter` interface
2. **Implement the required methods** defined in the interface
3. **Add a factory method** to `ObjectStorageFactory` to create instances of your adapter
4. **Register your adapter** with the application if necessary

### Example: Creating an FTP Adapter

Here's an example implementation of an FTP adapter:

```python
from abi.services.object_storage.ObjectStoragePort import IObjectStorageAdapter, Exceptions
from queue import Queue
from typing import Optional
import ftplib
import io
import os

class ObjectStorageSecondaryAdapterFTP(IObjectStorageAdapter):
    """FTP implementation of the Object Storage adapter."""
    
    def __init__(self, host: str, username: str, password: str, base_path: str = ""):
        """Initialize FTP adapter with connection details.
        
        Args:
            host (str): FTP server hostname or IP
            username (str): FTP username
            password (str): FTP password
            base_path (str, optional): Base path to prepend to all operations. Defaults to empty string.
        """
        self.host = host
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip('/')  # Remove trailing slash if present
        
    def __get_connection(self) -> ftplib.FTP:
        """Create and return a new FTP connection.
        
        Returns:
            ftplib.FTP: Connected FTP client
        """
        ftp = ftplib.FTP(self.host)
        ftp.login(self.username, self.password)
        return ftp
        
    def __get_full_path(self, prefix: str, key: str = None) -> str:
        """Construct full path including base path.
        
        Args:
            prefix (str): Prefix/folder path
            key (str, optional): Object key name
            
        Returns:
            str: Full path
        """
        if key is None:
            return f"{self.base_path}/{prefix}".strip('/')
        return f"{self.base_path}/{prefix}/{key}".strip('/')
        
    def __directory_exists(self, ftp: ftplib.FTP, path: str) -> bool:
        """Check if a directory exists in FTP server.
        
        Args:
            ftp (ftplib.FTP): FTP connection
            path (str): Path to check
            
        Returns:
            bool: True if exists, raises exception if not
        """
        current = ftp.pwd()
        try:
            ftp.cwd(path)
            ftp.cwd(current)  # Go back to previous directory
            return True
        except ftplib.error_perm:
            raise Exceptions.ObjectNotFound(f"Directory {path} not found")
            
    def __file_exists(self, ftp: ftplib.FTP, path: str) -> bool:
        """Check if a file exists in FTP server.
        
        Args:
            ftp (ftplib.FTP): FTP connection
            path (str): Path to check
            
        Returns:
            bool: True if exists, raises exception if not
        """
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        
        try:
            # Change to parent directory
            if directory:
                ftp.cwd(directory)
                
            # Check if file exists in directory listing
            file_list = ftp.nlst()
            if filename not in file_list:
                raise Exceptions.ObjectNotFound(f"File {path} not found")
                
            return True
        except ftplib.error_perm:
            raise Exceptions.ObjectNotFound(f"Path {path} not found")
            
    def __create_directories(self, ftp: ftplib.FTP, path: str) -> None:
        """Create directories recursively in FTP server.
        
        Args:
            ftp (ftplib.FTP): FTP connection
            path (str): Path to create
        """
        if not path:
            return
            
        path_parts = path.split('/')
        current_path = ""
        
        for part in path_parts:
            if not part:
                continue
                
            current_path += f"/{part}"
            try:
                ftp.cwd(current_path)
            except ftplib.error_perm:
                ftp.mkd(current_path)
    
    def get_object(self, prefix: str, key: str) -> bytes:
        """Get object from FTP server.
        
        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name
            
        Returns:
            bytes: Object content
        """
        ftp = self.__get_connection()
        path = self.__get_full_path(prefix, key)
        
        # Check if file exists
        self.__file_exists(ftp, path)
        
        # Retrieve file content
        buffer = io.BytesIO()
        ftp.retrbinary(f"RETR {path}", buffer.write)
        buffer.seek(0)
        content = buffer.read()
        
        ftp.quit()
        return content
    
    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        """Put object into FTP server.
        
        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name
            content (bytes): Content to upload
        """
        ftp = self.__get_connection()
        path = self.__get_full_path(prefix, key)
        directory = os.path.dirname(path)
        
        # Create directories if they don't exist
        self.__create_directories(ftp, directory)
        
        # Upload file content
        buffer = io.BytesIO(content)
        ftp.storbinary(f"STOR {path}", buffer)
        
        ftp.quit()
    
    def delete_object(self, prefix: str, key: str) -> None:
        """Delete object from FTP server.
        
        Args:
            prefix (str): Prefix/folder path
            key (str): Object key name
        """
        ftp = self.__get_connection()
        path = self.__get_full_path(prefix, key)
        
        # Check if file exists
        self.__file_exists(ftp, path)
        
        # Delete file
        ftp.delete(path)
        
        ftp.quit()
    
    def list_objects(self, prefix: str, queue: Optional[Queue] = None) -> list[str]:
        """List objects in FTP server with given prefix.
        
        Args:
            prefix (str): Prefix/folder path to list
            queue (Optional[Queue], optional): Queue to put results into
            
        Returns:
            list[str]: List of object paths
        """
        ftp = self.__get_connection()
        path = self.__get_full_path(prefix)
        
        # Check if directory exists
        self.__directory_exists(ftp, path)
        
        # List directory contents
        ftp.cwd(path)
        file_list = ftp.nlst()
        
        # Format results
        results = [f"{prefix}/{f}" for f in file_list if f not in ['.', '..']]
        
        # Add to queue if provided
        if queue:
            for result in results:
                queue.put(result)
                
        ftp.quit()
        return results
```

### Add a Factory Method

To make your adapter available through the factory pattern, add a new method to the `ObjectStorageFactory` class:

```python
# In lib/abi/services/object_storage/ObjectStorageFactory.py

@staticmethod
def ObjectStorageServiceFTP(host: str, username: str, password: str, base_path: str = "") -> ObjectStorageService:
    """Create an Object Storage Service using FTP as the backend.
    
    Args:
        host (str): FTP server hostname or IP
        username (str): FTP username
        password (str): FTP password
        base_path (str, optional): Base path for all operations. Defaults to empty string.
        
    Returns:
        ObjectStorageService: Configured service instance
    """
    from abi.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFTP import ObjectStorageSecondaryAdapterFTP
    return ObjectStorageService(ObjectStorageSecondaryAdapterFTP(host, username, password, base_path))
```

### Usage Example

You can now use your FTP adapter in your application:

```python
from abi.services.object_storage.ObjectStorageFactory import ObjectStorageFactory

# Create an FTP-based storage service
storage = ObjectStorageFactory.ObjectStorageServiceFTP(
    host="ftp.example.com",
    username="user",
    password="pass",
    base_path="/backups"
)

# Now you can use the storage service with the same interface
storage.put_object("users", "data.json", json_data_bytes)
content = storage.get_object("users", "data.json")
files = storage.list_objects("users")
storage.delete_object("users", "data.json")
```

### Key Considerations When Creating a New Adapter

1. **Error Handling**: Ensure your adapter properly translates storage-specific errors to the expected exceptions defined in the `Exceptions` class.
2. **Performance**: Consider optimizing operations for your specific storage backend, such as connection pooling or caching.
3. **Security**: Handle credentials securely and consider using environment variables or a secret management system.
4. **Testing**: Create comprehensive tests for your adapter to ensure it behaves consistently with other adapters.
5. **Documentation**: Update the documentation with details about your new adapter and its specific configuration options.

By following these steps, you can extend the Object Storage Service to work with any storage backend that provides a compatible API.