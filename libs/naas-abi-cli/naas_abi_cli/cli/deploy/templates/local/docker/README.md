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
│   └── Dockerfile.linux.x86_64     # Linux x86_64 optimized build
├── scripts/
│   └── cleanup.sh                  # Docker cleanup utilities
└── README.md                       # This documentation
```

## 🎯 Purpose & Organization

### **compose/**
Contains Docker Compose configurations for orchestrating multi-container applications:
- **`docker-compose.yml`** - Main service orchestration (Apache Jena Fuseki, PostgreSQL, Dagster, etc.)

### **images/**
Contains all Dockerfile variants for different deployment scenarios:
- **`Dockerfile`** - Standard application container
- **`Dockerfile.linux.x86_64`** - Optimized for Linux x86_64 architecture

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

```

### Running Services
```bash
# Start all local services
docker compose -f docker-compose.yml up -d

# Start specific service
docker compose -f docker-compose.yml up fuseki
```

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
