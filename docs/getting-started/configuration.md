# Configuration Guide

This guide explains how to configure ABI for different use cases and environments.

## Configuration File

ABI can be configured using a YAML configuration file located at `config/abi.yaml`. 

### Example Configuration

```yaml
# config/abi.yaml
system:
  log_level: INFO
  environment: development  # development, production, test
  
database:
  type: postgresql
  host: localhost
  port: 5432
  name: abi_db
  user: abi_user
  
integrations:
  enabled:
    - google_sheets
    - slack
    - jira
  
ontology:
  store_type: triplestore  # triplestore, neo4j
  endpoint: http://localhost:8890/sparql
  
api:
  host: 0.0.0.0
  port: 8000
  debug: true
  cors_origins:
    - http://localhost:3000
```

## Environment Variables

You can override configuration settings using environment variables. Environment variables take precedence over the configuration file.

### Required Environment Variables

- `ABI_SECRET_KEY`: Secret key for session encryption
- `ABI_DB_PASSWORD`: Database password

### Optional Environment Variables

- `ABI_ENVIRONMENT`: Set to `development`, `production`, or `test`
- `ABI_LOG_LEVEL`: Set to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`
- `ABI_API_PORT`: Port for the API server

### Example `.env` File

```
ABI_SECRET_KEY=your-secret-key
ABI_DB_PASSWORD=your-db-password
ABI_ENVIRONMENT=development
ABI_LOG_LEVEL=INFO
ABI_API_PORT=8000
```

## Configuration Profiles

ABI supports different configuration profiles for different environments.

### Available Profiles

- `development`: For local development
- `production`: For production deployment
- `test`: For running tests

### Selecting a Profile

Set the `ABI_ENVIRONMENT` environment variable to select a profile:

```bash
export ABI_ENVIRONMENT=production
```

## Integration Configuration

Each integration has its own configuration section in the config file.

### Example Integration Configuration

```yaml
integrations:
  google_sheets:
    client_id: your-client-id
    client_secret: your-client-secret
    
  slack:
    api_token: your-api-token
    
  jira:
    url: https://your-jira-instance.atlassian.net
    username: your-username
    api_token: your-api-token
```

## Ontology Configuration

Configure the ontology storage system:

```yaml
ontology:
  store_type: triplestore
  endpoint: http://localhost:8890/sparql
  auth_enabled: false
  username: dba
  password: dba
```

## Logging Configuration

Configure logging behavior:

```yaml
logging:
  level: INFO
  file: logs/abi.log
  max_size: 10MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## Next Steps

- Return to the [Quick Start Guide](quick-start.md)
- Learn about [ABI Architecture](../concepts/architecture.md) 