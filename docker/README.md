# Docker Configuration

> **Centralized Docker configuration and containerization assets for ABI**

This directory contains all Docker-related files organized for maintainability and clarity, following industry best practices used by major open source projects.

## 📁 Directory Structure

```
docker/
├── compose/
│   └── docker-compose.yml          # Main orchestration configuration
├── images/
│   ├── Dockerfile                  # Primary application container
│   ├── Dockerfile.linux.x86_64     # Linux x86_64 optimized build
│   └── Dockerfile.mcp              # MCP server variant
├── scripts/
│   └── cleanup.sh                  # Docker cleanup utilities
└── README.md                       # This documentation
```

## 🎯 Purpose & Organization

### **compose/**
Contains Docker Compose configurations for orchestrating multi-container applications:
- **`docker-compose.yml`** - Main service orchestration (Oxigraph, PostgreSQL, Dagster, etc.)

### **images/**
Contains all Dockerfile variants for different deployment scenarios:
- **`Dockerfile`** - Standard application container
- **`Dockerfile.linux.x86_64`** - Optimized for Linux x86_64 architecture
- **`Dockerfile.mcp`** - Model Context Protocol server configuration

### **scripts/**
Docker-related utility scripts:
- **`cleanup.sh`** - Comprehensive Docker cleanup to resolve conflicts

## 🚀 Usage

### Building Images
```bash
# Build standard image
docker build -f docker/images/Dockerfile -t abi .

# Build Linux x86_64 optimized
docker build -f docker/images/Dockerfile.linux.x86_64 -t abi-linux .

# Build MCP server
docker build -f docker/images/Dockerfile.mcp -t abi-mcp .
```

### Running Services
```bash
# Start all local services
docker-compose -f docker-compose.yml --profile local up -d

# Start specific service
docker-compose -f docker-compose.yml up oxigraph
```

### Existing PostgreSQL volumes

New volumes create the dedicated DuckLake catalog database automatically. Init
scripts do not run again for an existing volume, so apply the idempotent script
once after upgrading:

```bash
docker compose exec -T postgres psql -U "${POSTGRES_USER:-abi}" -d postgres \
  -f /docker-entrypoint-initdb.d/005-create-ducklake-db.sql
```

This script only provisions the PostgreSQL database and grants. The dataset
adapter initializes and migrates DuckLake metadata when it connects.

The DuckLake catalog and `storage/datasets/` must be backed up and
restored at the same point in time. `abi stack snapshot create` does this by
stopping the stack before it archives both PostgreSQL and `storage/`.

### Cleanup
```bash
# Run comprehensive cleanup
./docker/scripts/cleanup.sh
```

## 🔧 Makefile Integration

All Docker operations are integrated into the main Makefile:

```bash
make local-up          # Start local development environment
make api-prod          # Build and run production API
make docker-cleanup    # Run Docker cleanup
make build.linux.x86_64  # Build Linux x86_64 image
```

## 📋 Best Practices

1. **Organized Structure**: All Docker files are centralized and categorized
2. **Clear Naming**: File names indicate their specific purpose and target
3. **Documentation**: Each component is documented for maintainability
4. **Integration**: Seamless integration with existing build and deployment workflows

This organization follows patterns established by major projects like Kubernetes, Prometheus, and HashiCorp Vault for maximum developer familiarity and maintainability.
