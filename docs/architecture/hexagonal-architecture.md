# Hexagonal Architecture in ABI

ABI implements the Hexagonal Architecture pattern (also known as Ports & Adapters) to create a flexible, maintainable system that can easily adapt to changing requirements and technologies.

## Core Concept

The Hexagonal Architecture separates the core application logic from external concerns by:
1. Defining clear interfaces ("ports") for all external interactions
2. Implementing adapters that translate between the core application and external systems
3. Ensuring the application core depends only on abstractions, not concrete implementations

This approach allows ABI to be deployed in various environments while maintaining consistent behavior.

## Implementation in ABI Services

Each service in ABI follows the Hexagonal Architecture pattern:

1. **Core Logic**: Contains the business rules and application logic
2. **Ports**: Defines the interfaces for external interactions
3. **Adapters**: Implements the concrete integrations with external systems


## Ports (Interfaces)

In ABI, ports are defined as Python interfaces (abstract base classes) that specify the capabilities of a service:

1. **Primary Ports**: Define how the application can be used (Service APIs)
   - Example: `ITripleStoreService` interface

2. **Secondary Ports**: Define what the application needs from external systems
   - Example: `IObjectStorageAdapter` interface

## Adapters (Implementations)

Adapters implement the port interfaces and connect the application to external systems:

1. **Primary Adapters**: Consume the application's primary ports
   - Examples: FastAPI routes, CLI commands, LLM tools

2. **Secondary Adapters**: Implement secondary ports for various backends
   - Examples: `TripleStoreServiceFilesystem`, `ObjectStorageSecondaryAdapterS3`

## Benefits in ABI

This architecture provides several advantages for ABI:

1. **Backend Flexibility**: Easily swap implementations (e.g., from local filesystem to AWS S3)
2. **Testing**: Create mock adapters for testing without external dependencies
3. **Separation of Concerns**: Clean boundaries between components
4. **Extensibility**: Add new adapters without modifying core logic

## Example Service: Secret Service

The Secret Service in ABI could connect to various backend systems through different adapters to store and retrieve secrets:
- Hashicorp Vault
- AWS Secrets Manager
- Azure Key Vault
- Environment Variables
- Local File System
- Google Cloud Secret Manager
- Kubernetes Secrets

This allows the same interface to be used regardless of where secrets are actually stored.