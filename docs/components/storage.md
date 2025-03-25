# Storage Architecture

ABI implements a flexible, multi-level storage system that separates storage location concerns from the business logic. The storage system is designed to work seamlessly across different environments (development, production) and storage backends.

## Design Philosophy

The storage system is designed to be:
1. **Backend-agnostic**: Support multiple storage backends (filesystem, S3, etc.)
2. **Synchronized**: Keep local and remote storage in sync
3. **Structured**: Organize data in a consistent directory structure
4. **Modular**: Separate different types of data (documents, triples, vectors)

## Storage Types

ABI manages four primary types of storage:

1. **Data Store**: Structured and unstructured data, raw documents and files
1. **Triple Store**: Semantic data in RDF/Turtle format
2. **Vector Store**: Vector embeddings for machine learning