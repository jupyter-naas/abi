# Remote Storage Implementation

This document explains how the remote storage system is implemented in the codebase, focusing on the synchronization of local storage to a remote location, the architecture, key components, and how the various storage providers work together.

## Architecture Overview

The remote storage system follows a layered, adapter-based architecture designed for flexibility:

````
┌─────────────────┐     ┌───────────────────┐
│ Storage Scripts │────>│ Storage Service   │
│ (push/pull)     │     │ (Domain Layer)    │
└─────────────────┘     └────────┬──────────┘
                                 │
                                 ▼
                        ┌───────────────────┐
                        │ Storage Adapter   │
                        │ (Interface)       │
                        └────────┬──────────┘
                                 │
                      ┌──────────┴───────────┐
                      │                      │
            ┌─────────▼────────┐  ┌──────────▼─────────┐  ┌──────────▼─────────┐
            │ Local Filesystem │  │ AWS S3 Adapter     │  │ Other Providers     │
            │    Adapter       │  │ (boto3-based)      │  │ (GCP, Azure, etc.)  │
            └──────────────────┘  └────────────────────┘  └────────────────────┘
````

## Make Commands for Storage Operations

The codebase provides convenient Makefile targets to handle storage operations:

````bash
# Pull data from remote storage to local
make storage-pull

# Push local data to remote storage
make storage-push
````

These commands:
1. Ensure the virtual environment is set up first (through the `.venv` dependency)
2. Run the storage scripts inside a Docker container
3. Pipe the output of the scripts (AWS CLI commands) to the shell for execution:

````makefile
storage-pull: .venv
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python scripts/storage_pull.py | sh'

storage-push: .venv
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python scripts/storage_push.py | sh'
````

These Make targets provide a convenient way to execute the underlying storage scripts in a consistent environment.

## Core Components

### 1. Interface Definitions

The system is built on clean interfaces defined in `ObjectStoragePort.py`:

````python
class IObjectStorageAdapter(ABC):
    @abstractmethod
    def get_object(self, prefix: str, key: str) -> bytes:
        pass
    
    @abstractmethod
    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        pass
    
    @abstractmethod
    def delete_object(self, prefix: str, key: str) -> None:
        pass
    
    @abstractmethod
    def list_objects(self, prefix: str) -> list[str]:
        pass
````

These interfaces ensure all storage providers implement the same core functionality.

### 2. Factory Pattern

The `ObjectStorageFactory` creates appropriate storage service instances based on the desired provider:

````python
class ObjectStorageFactory:
    @staticmethod
    def ObjectStorageServiceFS__find_storage(needle: str = 'storage') -> ObjectStorageService:
        # Creates filesystem storage service by finding storage directory
        # ...
    
    @staticmethod
    def ObjectStorageServiceS3(access_key_id, secret_access_key, bucket_name, base_prefix, session_token=None):
        # Creates S3 storage service
        # ...
        
    @staticmethod
    def ObjectStorageServiceNaas(naas_api_key, workspace_id, storage_name, base_prefix=""):
        # Creates Naas storage service
        # ...
````

This factory pattern makes it easy to switch between storage providers or add new ones.

### 3. The Storage Service

The `ObjectStorageService` implements the domain interface and delegates to the appropriate adapter:

````python
class ObjectStorageService(IObjectStorageDomain):
    def __init__(self, adapter: IObjectStorageAdapter):
        self.adapter = adapter
        
    def get_object(self, prefix: str, key: str) -> bytes:
        return self.adapter.get_object(prefix, key)
    
    # Other methods similarly delegate to the adapter
````

## Storage Provider Implementations

### 1. Local Filesystem Adapter

The `ObjectStorageSecondaryAdapterFS` implements storage operations using the local filesystem:

````python
class ObjectStorageSecondaryAdapterFS(IObjectStorageAdapter):
    def __init__(self, base_path: str):
        self.base_path = base_path
        
    def get_object(self, prefix: str, key: str) -> bytes:
        # Read file from filesystem
        with open(os.path.join(self.base_path, prefix, key), "rb") as f:
            return f.read()
    # Other methods similarly work with local files
````

### 2. AWS S3 Adapter

The `ObjectStorageSecondaryAdapterS3` uses boto3 to interact with S3:

````python
class ObjectStorageSecondaryAdapterS3(IObjectStorageAdapter):
    def __init__(self, bucket_name, access_key_id, secret_access_key, base_prefix="", session_token=None):
        self.bucket_name = bucket_name
        self.base_prefix = base_prefix.rstrip('/')
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token
        )
    
    def get_object(self, prefix: str, key: str) -> bytes:
        # Get object from S3 using boto3
        response = self.s3_client.get_object(
            Bucket=self.bucket_name,
            Key=self.__get_full_key(prefix, key)
        )
        return response['Body'].read()
    # Other methods similarly use boto3
````

### 3. Naas Storage Adapter

The `ObjectStorageSecondaryAdapterNaas` is a special adapter that provides managed storage for Naas workspaces. It works by:

1. Obtaining temporary S3 credentials from the Naas API
2. Creating an S3 adapter with those credentials
3. Delegating all operations to that S3 adapter
4. Refreshing credentials automatically when they expire

````python
class ObjectStorageSecondaryAdapterNaas(IObjectStorageAdapter):
    def __init__(self, naas_api_key, workspace_id, storage_name, base_prefix=""):
        self.__naas_api_key = naas_api_key
        self.__workspace_id = workspace_id
        self.__storage_name = storage_name
        self.__base_prefix = base_prefix
        
    def ensure_credentials(self):
        # Fetch or refresh temporary S3 credentials
        # Creates an S3 adapter with those credentials
        
    def get_object(self, prefix: str, key: str) -> bytes:
        self.ensure_credentials()
        return self.__s3_adapter.get_object(prefix, key)
    # Other methods similarly ensure credentials and delegate
````

## Command-line Storage Operations

The system includes two main scripts for storage operations:

### 1. storage-push

The `storage_push.py` script:
1. Retrieves storage credentials using `get_storage_credentials`
2. Constructs an AWS CLI command to synchronize local files to S3
3. Uses `aws s3 sync` for efficient delta-based uploads

````python
def get_storage_credentials(naas_api_key, workspace_id, storage_name):
    # Makes API call to get temporary S3 credentials
    # Returns bucket, access_key_id, secret_access_key, session_token

if __name__ == "__main__":
    naas_api_key, workspace_id, storage_name = get_config()
    bucket, access_key_id, secret_access_key, session_token = get_storage_credentials(naas_api_key, workspace_id, storage_name)
    
    print(f'AWS_ACCESS_KEY_ID={access_key_id} AWS_SECRET_ACCESS_KEY={secret_access_key} AWS_SESSION_TOKEN={session_token} aws s3 sync --follow-symlinks --delete storage/ {bucket}/storage')
````

### 2. storage-pull

The `storage_pull.py` script works similarly but in reverse:
1. Retrieves storage credentials 
2. Constructs an AWS CLI command to synchronize S3 files to local storage
3. Uses `aws s3 sync` for efficient delta-based downloads

````python
if __name__ == "__main__":
    naas_api_key, workspace_id, storage_name = get_config()
    bucket, access_key_id, secret_access_key, session_token = get_storage_credentials(naas_api_key, workspace_id, storage_name)
    
    print(f'AWS_ACCESS_KEY_ID={access_key_id} AWS_SECRET_ACCESS_KEY={secret_access_key} AWS_SESSION_TOKEN={session_token} aws s3 sync --delete {bucket}/storage storage/')
````

## Integration with Other Services

The storage system integrates with:

1. **DVC (Data Version Control)**: The `setup_dvc.py` script configures DVC to use the same S3 storage, enabling version control for data files.

2. **Naas Workspace**: The system can automatically detect when running in a Naas workspace and use the appropriate storage configuration.

3. **Docker**: Environment variables can be passed to Docker containers to enable direct S3 access.

## Extension and Customization

To add support for a new storage provider:

1. Create a new adapter class that implements `IObjectStorageAdapter`
2. Add a factory method to `ObjectStorageFactory`
3. Use the new provider in your code via the factory

For example, the codebase includes a partial implementation of `GCPStorageIntegration` showing how to integrate with Google Cloud Storage.

## Credential Management

The system uses different approaches for credentials:

1. **Environment Variables**: For direct AWS S3 access
2. **Naas API**: For Naas workspace storage, obtains temporary credentials
3. **Service Account Files**: For GCP Storage

Credentials are automatically refreshed when needed, particularly for temporary credentials from Naas.
