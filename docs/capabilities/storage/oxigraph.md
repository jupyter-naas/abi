# Oxigraph Triple Store

[Source Code](../../../lib/abi/services/triple_store/adaptors/secondary/Oxigraph.py)

## Overview

Oxigraph is a lightweight, high-performance graph database that provides RDF storage and SPARQL query capabilities. The ABI framework includes built-in support for Oxigraph through a dedicated adapter, making it easy to use Oxigraph as your triple store backend.

Oxigraph is particularly well-suited for:
- Development environments with limited resources
- Apple Silicon Macs (native ARM64 support, no emulation needed)
- Applications requiring a minimal footprint triple store
- Projects needing full SPARQL 1.1 compliance
- Embedded deployments and edge computing scenarios

## Features

- **Lightweight**: Minimal resource consumption compared to Java-based alternatives
- **Fast Startup**: Typically ready in seconds, not minutes
- **Native Performance**: No JVM overhead, pure Rust implementation
- **Apple Silicon Native**: Runs natively on ARM64 without emulation
- **Automatic Container Management**: In development mode, ABI automatically starts and manages the Oxigraph Docker container
- **Health Checks**: Built-in health monitoring ensures Oxigraph is ready before use
- **Full SPARQL Support**: Complete SPARQL 1.1 query and update operations
- **REST API Integration**: Clean HTTP-based communication with Oxigraph
- **Docker Compose Integration**: Seamless integration with the project's Docker infrastructure

## Quick Start

### Development Environment

When you run ABI in development mode, Oxigraph will automatically start if it's not already running:

```bash
make chat-abi-agent
```

The CLI will:
1. Check if Oxigraph is running on port 7878
2. Start the Docker container if needed
3. Wait for Oxigraph to be ready
4. Configure the `OXIGRAPH_URL` in your `.env` file

### Manual Container Management

You can also manage the Oxigraph container manually:

```bash
# Start Oxigraph
make oxigraph-up

# Stop Oxigraph
make oxigraph-down

# Check Oxigraph status
make oxigraph-status

# Start all development containers
make dev-up

# Stop all development containers
make dev-down
```

### Accessing Oxigraph

Once running, you can access Oxigraph at:
- **Base URL**: http://localhost:7878
- **SPARQL Query Endpoint**: http://localhost:7878/query
- **SPARQL Update Endpoint**: http://localhost:7878/update
- **Store Endpoint**: http://localhost:7878/store

## Configuration

### Environment Variables

Configure Oxigraph using environment variables in your `.env` file:

```bash
# Oxigraph configuration
OXIGRAPH_URL=http://localhost:7878  # Default for local development
```

### Docker Compose Configuration

Oxigraph is configured in `docker-compose.yml` with:
- **Port**: 7878 (mapped to host)
- **Volume**: Persistent storage for data
- **Health Check**: Monitors SPARQL endpoint availability
- **Minimal Memory**: Typically uses < 100MB RAM

## Using Oxigraph in Your Code

### Basic Usage

```python
from abi.services.triple_store.TripleStoreFactory import TripleStoreFactory
from rdflib import Graph, URIRef, Literal, RDF

# Create Oxigraph triple store service
triple_store = TripleStoreFactory.TripleStoreServiceOxigraph()

# Create and insert data
g = Graph()
g.add((URIRef("http://example.org/alice"), 
       RDF.type, 
       URIRef("http://example.org/Person")))
g.add((URIRef("http://example.org/alice"), 
       URIRef("http://example.org/name"), 
       Literal("Alice")))

triple_store.insert(g)

# Query data
results = triple_store.query("""
    SELECT ?person ?name WHERE {
        ?person a <http://example.org/Person> .
        ?person <http://example.org/name> ?name .
    }
""")

for row in results:
    print(f"Person: {row.person}, Name: {row.name}")
```

### Advanced Configuration

```python
# Use custom Oxigraph instance
triple_store = TripleStoreFactory.TripleStoreServiceOxigraph(
    oxigraph_url="http://your-oxigraph-server:7878"
)
```

## Production Deployment

For production environments, you have several options:

### 1. Using Docker Compose (Recommended)

```bash
# Start production profile
docker-compose --profile prod up -d
```

### 2. External Oxigraph Instance

Configure your `.env` file to point to an external Oxigraph instance:

```bash
OXIGRAPH_URL=https://oxigraph.your-domain.com
```

### 3. Cloud Deployment

Oxigraph can be deployed on various cloud platforms:
- AWS ECS/Fargate (minimal container)
- Google Cloud Run (serverless)
- Azure Container Instances
- Kubernetes clusters (lightweight pods)
- Edge computing devices (IoT)

## Performance

### Memory Efficiency

Oxigraph uses significantly less memory than Java-based alternatives:
- **Idle**: ~20-50MB RAM
- **Under Load**: ~100-500MB RAM (depending on dataset size)
- **Startup Time**: 1-3 seconds

### Query Performance

Oxigraph provides excellent query performance:
- Optimized for read-heavy workloads
- Efficient SPARQL query execution
- Fast bulk loading via Turtle/N-Triples

## Troubleshooting

### Container Won't Start

```bash
# Check Docker logs
docker-compose logs oxigraph

# Verify port availability
lsof -i :7878

# Reset Oxigraph data
docker-compose down -v
docker-compose --profile dev up -d oxigraph
```

### Connection Issues

```bash
# Test Oxigraph endpoint
curl "http://localhost:7878/query?query=SELECT%20*%20WHERE%20%7B%20%3Fs%20%3Fp%20%3Fo%20%7D%20LIMIT%201"

# Check container status
docker-compose ps oxigraph
```

### Performance Issues

1. Check available disk space for Oxigraph data volume
2. Monitor query complexity and optimize SPARQL queries
3. Use LIMIT clauses for large result sets
4. Consider using CONSTRUCT queries for graph patterns

## Best Practices

1. **Data Persistence**: The Docker volume ensures data persists between container restarts
2. **Backup Strategy**: Regularly backup the `oxigraph_data` volume
3. **Query Optimization**: Use SPARQL FILTER and LIMIT clauses to improve query performance
4. **Bulk Loading**: Use Turtle format for efficient bulk data loading
5. **Monitoring**: Monitor container logs and resource usage in production

## Key Advantages

1. **Resource Efficiency**: Minimal memory footprint (~50-100MB)
2. **Fast Startup**: Ready in 1-3 seconds
3. **Apple Silicon Native**: Full ARM64 support without emulation
4. **Simplicity**: No JVM or complex configuration required
5. **Small Container**: ~50MB image size
6. **Modern Architecture**: Written in Rust with excellent performance characteristics

## Additional Resources

- [Oxigraph Official Repository](https://github.com/oxigraph/oxigraph)
- [Oxigraph Documentation](https://github.com/oxigraph/oxigraph/wiki)
- [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/)
- [RDF Primer](https://www.w3.org/TR/rdf-primer/)
- [Oxigraph Python Client](https://pypi.org/project/pyoxigraph/)