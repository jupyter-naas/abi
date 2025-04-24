# Storage

Storage is managed through service abstractions that allow seamless switching between local and production environments. 
In production, we utilize AWS S3 for storage capabilities.
For local development, the system defaults to local file storage when ENV=dev is set in the .env configuration file.

## Manage Environment

The environment is managed through the `.env` file and the `ENV` variable.
By default, the system will use the `dev` environment so everything will be stored locally.
If you want to use the production environment, you need to set the `ENV` variable to `prod` and the system will use the production storage.

## Directory Structure

The storage system provides a filesystem-based storage layer that serves as the foundation for several data storage types:

- **Datastore**: For unstructured data, raw documents and files from modules
- **Triplestore**: For semantic data in RDF/Turtle format with triples and views.
- **Vectorstore**: For embedding vectors used in machine learning and retrieval systems

The standard storage directory structure is organized as follows:

storage/
├── datastore/                # Combined storage for documents and structured/unstructured data
│   ├── module_1/            # First module data
│   ├── module_2/            # Second module data
│   └── module_3/            # Third module data
│
├── triple_store/             # Semantic data storage
│   ├── ontologies/           # Ontology definitions (.owl, .rdf)
│   └── triples/              # RDF triple data (.ttl)
│
└── vector_store/             # Vector embeddings
    ├── embeddings/           # Raw vector data
    ├── indexes/              # Vector search indexes
    └── metadata/             # Associated metadata

### Datastore

The `datastore/` directory is organized by module and must serve as a combined storage for documents and structured/unstructured data.
It stores raw data (txt, csv, json, etc.) from modules integrations so it can be used by pipelines and stored in triple store.

#### Synchronization with Remote Storage

The local storage can be synchronized with remote storage using the Makefile commands:

```bash
# Pull data from remote storage to local
make storage-pull

# Push local data to remote storage
make storage-push
```

### Triple Store

#### Structure

The `triple_store/` stores all triples from ontologies in `src/core` and `src/custom` and also triples added by pipelines.

It is organized in the following directories:
  
- **triples/**: Contains instance data in the form of RDF triples
  - `.ttl` (Turtle) files each represent a specific subject with a unique ID generated using the `uuid` library
  - Filenames are created by hashing the subject URI using SHA-256 to ensure uniqueness

- **views/**: Contains symbolic views of triples organized by subject type (`rdf:type`)
  - View names follow the format `{rdfs:label}_{unique_id}` (e.g., "Commercial Organization_ont00000443")
  - Each `.ttl` file contains a symbolic representation of related triples from the `triples` directory

#### Production Management

Triple store can be used in local development environment or in production.

In production, triplestore will be stored in AWS S3 bucket to be accessible by remote agents.

To manage production triplestore, the following Make commands can be used:

- Remove all triples from production and create a backup
```bash
# Remove production triplestore 
make triplestore-prod-remove
```

- Override production triplestore with local triplestore
```bash
# Override production triplestore
make triplestore-prod-override
```

- Pull production triplestore to local
```bash
make triplestore-prod-pull
```

### Vector Store

The `vector_store/` directory is optimized for machine learning applications:

- **embeddings/**: Contains raw vector data, typically in binary formats
  - Organized by model and dimension (e.g., `bert-base-768d/`)
  
- **indexes/**: Contains optimized search structures
  - FAISS, Annoy, or other vector index formats
  - Configured for specific similarity metrics (cosine, euclidean, etc.)
  
- **metadata/**: Contains JSON files that map vectors to their source data
  - Provides context and additional information for each embedding