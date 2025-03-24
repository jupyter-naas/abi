# Local Storage

This document provides an overview of the implementation of the local storage system within the codebase, emphasizing the organization of files and directories as well as the foundational architecture. It is designed to synchronize seamlessly with the remote storage feature, facilitating connections to object storage solutions such as S3, which the API utilizes to deliver data effectively.

## Overview

The local storage system provides a filesystem-based storage layer that serves as the foundation for several data storage types:

- **Datastore**: For unstructured data, raw documents and files
- **Triplestore**: For semantic data in RDF/Turtle format 
- **Vectorstore**: For embedding vectors used in machine learning and retrieval systems

The local storage implementation uses a clean abstraction layer that allows consistent access patterns regardless of whether the data is stored locally or remotely.

## Directory Structure

The standard local storage directory structure is organized as follows:

storage/
├── datastore/                # Combined storage for documents and structured/unstructured data
│   ├── pdf/                  # PDF documents
│   ├── docx/                 # Word documents
│   ├── presentations/        # PowerPoint files
│   ├── images/               # Image files
│   ├── raw/                  # Unprocessed data
│   ├── processed/            # Transformed data
│   ├── intermediate/         # Temporary processing results
│   └── output/               # Final data products
│
├── triplestore/             # Semantic data storage
│   ├── ontologies/           # Ontology definitions (.owl, .rdf)
│   └── triples/              # RDF triple data (.ttl)
│
└── vectorstore/             # Vector embeddings
    ├── embeddings/           # Raw vector data
    ├── indexes/              # Vector search indexes
    └── metadata/             # Associated metadata

### Triple Store Structure

The `triplestore/` directory follows semantic web standards:

- **ontologies/**: Contains schema definitions and ontology models
  - `.owl` files define formal ontologies with classes, properties, and rules
  - `.rdf` files provide basic RDF Schema definitions
  
- **triples/**: Contains instance data in the form of RDF triples
  - `.ttl` (Turtle) files are the primary format for human-readable triples
  - Data is organized by domain or source (e.g., `customers.ttl`, `products.ttl`)

### Vector Store Structure

The `vectorstore/` directory is optimized for machine learning applications:

- **embeddings/**: Contains raw vector data, typically in binary formats
  - Organized by model and dimension (e.g., `bert-base-768d/`)
  
- **indexes/**: Contains optimized search structures
  - FAISS, Annoy, or other vector index formats
  - Configured for specific similarity metrics (cosine, euclidean, etc.)
  
- **metadata/**: Contains JSON files that map vectors to their source data
  - Provides context and additional information for each embedding

## Implementation

The local storage is implemented by the `ObjectStorageSecondaryAdapterFS` class which provides a filesystem adapter that conforms to the `IObjectStorageAdapter` interface:

### Auto-Discovery

The system automatically discovers the storage directory by looking for a directory named "storage" starting from the current working directory and traversing up to the root. This makes it convenient to access the storage directory from any location in the project.

## Usage

To use the local storage system programmatically:

```python
# Get a storage service instance
from lib.abi.services.object_storage.ObjectStorageFactory import ObjectStorageFactory

# Auto-discover storage directory
storage_service = ObjectStorageFactory.ObjectStorageServiceFS__find_storage()

# Or specify a path explicitly
storage_service = ObjectStorageFactory.ObjectStorageServiceFS("/path/to/storage")

# Basic operations
# Store a file
storage_service.put_object("triplestore/triples", "people.ttl", ttl_content)

# Retrieve a file
content = storage_service.get_object("data_lake/processed", "customers.json")

# List files in a directory
files = storage_service.list_objects("documents/pdf")

# Delete a file
storage_service.delete_object("vectorstore/embeddings", "temp_vectors.bin")
```

## Synchronization with Remote Storage

The local storage can be synchronized with remote storage using the Makefile commands:

```bash
# Pull data from remote storage to local
make storage-pull

# Push local data to remote storage
make storage-push
```

These commands automatically handle the authentication and execute the AWS S3 sync operations to efficiently transfer only changed files.

## Best Practices

1. **Follow the standard directory structure** to ensure consistency and compatibility with other system components.

2. **Use appropriate directories** for different types of data:
   - Document files → `datastore/documents/`
   - Raw data → `datastore/[module_name]/raw/`
   - Processed data → `datastore/[module_name]/processed/`
   - RDF triples → `triplestore/[module_name]/triples/`
   - Vector embeddings → `vectorstore/[module_name]/embeddings/`

3. **Use consistent naming conventions**:
   - Use lowercase for directories and filenames
   - Use underscores for spaces in filenames
   - Include dates in filenames where appropriate (YYYY-MM-DD format)
   - Use appropriate file extensions (.ttl, .json, .bin)

4. **Regularly synchronize** with remote storage to ensure data persistence and backup.

5. **Clean up temporary files** to prevent storage bloat and keep the system organized.
