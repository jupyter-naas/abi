# Environment Variables

This document provides a comprehensive list of environment variables used by the ABI framework, their purpose, and recommended values for different deployment environments.

## Overview

ABI uses environment variables for configuration to:

1. Keep sensitive information out of code
2. Allow different configurations for different environments
3. Enable easy integration with container orchestration platforms
4. Simplify deployment automation

## Loading Environment Variables

ABI loads environment variables in several ways:

1. **System Environment**: Variables set at the OS level
2. **`.env` File**: Local development uses a `.env` file in the project root
3. **Docker Environment**: Variables passed to containers
4. **Kubernetes Secrets/ConfigMaps**: For Kubernetes deployments

Priority order (highest to lowest):
1. System environment variables
2. `.env` file values
3. Default values in code

## Required Environment Variables

These variables must be set for ABI to function properly:

| Variable | Description | Example |
|----------|-------------|---------|
| `ABI_SECRET_KEY` | Secret key for cryptographic signing | `"h8dsh7we78d7we9d87e9zxc..."` |
| `ABI_DATABASE_URL` | PostgreSQL connection string | `"postgresql://user:pass@host:5432/dbname"` |
| `ABI_ONTOLOGY_ENDPOINT` | SPARQL endpoint for the ontology store | `"http://triplestore:3030/abi/sparql"` |
| `ABI_REDIS_URL` | Redis connection string | `"redis://redis:6379/0"` |

## Core Configuration Variables

These variables control the core ABI system:

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `ABI_ENVIRONMENT` | Deployment environment | `"development"` | `"development"`, `"staging"`, `"production"` |
| `ABI_LOG_LEVEL` | Logging verbosity | `"INFO"` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"` |
| `ABI_API_HOST` | Host to bind API server | `"0.0.0.0"` | Any valid hostname or IP |
| `ABI_API_PORT` | Port to bind API server | `8000` | Any valid port number |
| `ABI_WORKERS` | Number of API worker processes | `4` | Integer value |
| `ABI_WORKER_CONCURRENCY` | Concurrent tasks per worker | `8` | Integer value |
| `ABI_REQUEST_TIMEOUT` | API request timeout in seconds | `60` | Integer value |
| `ABI_MAX_CONTENT_LENGTH` | Maximum request content size (MB) | `100` | Integer value |
| `ABI_ENABLE_CORS` | Enable CORS for API | `"false"` | `"true"`, `"false"` |
| `ABI_CORS_ORIGINS` | Allowed CORS origins | `""` | Comma-separated list |
| `ABI_RATE_LIMIT_ENABLED` | Enable rate limiting | `"true"` | `"true"`, `"false"` |
| `ABI_RATE_LIMIT` | Requests per minute limit | `60` | Integer value |

## Authentication and Security Variables

These variables control authentication and security:

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `ABI_AUTH_ENABLED` | Enable authentication | `"true"` | `"true"`, `"false"` |
| `ABI_AUTH_METHOD` | Authentication method | `"jwt"` | `"jwt"`, `"api_key"`, `"oauth"` |
| `ABI_JWT_EXPIRATION` | JWT token expiration (seconds) | `3600` | Integer value |
| `ABI_JWT_REFRESH_EXPIRATION` | JWT refresh token expiration (seconds) | `86400` | Integer value |
| `ABI_PASSWORD_MIN_LENGTH` | Minimum password length | `8` | Integer value |
| `ABI_PASSWORD_COMPLEXITY` | Password complexity requirement | `"medium"` | `"low"`, `"medium"`, `"high"` |
| `ABI_MFA_ENABLED` | Enable multi-factor authentication | `"false"` | `"true"`, `"false"` |
| `ABI_FAILED_LOGIN_LIMIT` | Account lockout threshold | `5` | Integer value |
| `ABI_SESSION_TIMEOUT` | Session timeout in minutes | `30` | Integer value |

## Database Variables

These variables control database connections:

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `ABI_DATABASE_POOL_SIZE` | Database connection pool size | `10` | Integer value |
| `ABI_DATABASE_MAX_OVERFLOW` | Max extra connections | `20` | Integer value |
| `ABI_DATABASE_POOL_RECYCLE` | Connection recycle time (seconds) | `3600` | Integer value |
| `ABI_DATABASE_POOL_TIMEOUT` | Pool timeout (seconds) | `30` | Integer value |
| `ABI_DATABASE_ECHO` | Log SQL queries | `"false"` | `"true"`, `"false"` |
| `ABI_DATABASE_SSL_MODE` | PostgreSQL SSL mode | `"prefer"` | `"disable"`, `"allow"`, `"prefer"`, `"require"`, `"verify-ca"`, `"verify-full"` |

## Ontology Store Variables

These variables control the ontology store:

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `ABI_ONTOLOGY_STORE_TYPE` | Type of ontology store | `"fuseki"` | `"fuseki"`, `"neptune"`, `"virtuoso"` |
| `ABI_ONTOLOGY_USERNAME` | Ontology store username | `""` | String value |
| `ABI_ONTOLOGY_PASSWORD` | Ontology store password | `""` | String value |
| `ABI_ONTOLOGY_DEFAULT_GRAPH` | Default graph name | `"http://abi.example.org/graph"` | URI string |
| `ABI_ONTOLOGY_QUERY_TIMEOUT` | Query timeout in seconds | `30` | Integer value |
| `ABI_ONTOLOGY_MAX_RESULTS` | Maximum query results | `10000` | Integer value |

## Cache and Message Queue Variables

These variables control caching and message queuing:

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `ABI_REDIS_MAX_CONNECTIONS` | Redis connection pool size | `10` | Integer value |
| `ABI_CACHE_TTL` | Default cache TTL (seconds) | `300` | Integer value |
| `ABI_RESULT_CACHE_ENABLED` | Enable result caching | `"true"` | `"true"`, `"false"` |
| `ABI_RESULT_CACHE_TTL` | Result cache TTL (seconds) | `3600` | Integer value |
| `ABI_QUEUE_NAME` | Message queue name | `"abi_tasks"` | String value |
| `ABI_TASK_DEFAULT_TIMEOUT` | Default task timeout (seconds) | `300` | Integer value |
| `ABI_TASK_MAX_RETRIES` | Maximum task retry attempts | `3` | Integer value |
| `ABI_TASK_RETRY_DELAY` | Delay between retries (seconds) | `60` | Integer value |

## Integration Variables

These variables control integrations with external systems:

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `ABI_INTEGRATION_TIMEOUT` | Integration request timeout (seconds) | `30` | Integer value |
| `ABI_INTEGRATION_MAX_RETRIES` | Integration max retry attempts | `3` | Integer value |
| `ABI_INTEGRATION_RETRY_DELAY` | Integration retry delay (seconds) | `5` | Integer value |
| `ABI_INTEGRATION_TOKEN_*` | Integration specific tokens | | Replace * with integration name (uppercase) |
| `ABI_INTEGRATION_URL_*` | Integration specific URLs | | Replace * with integration name (uppercase) |

## AI Model Variables

These variables control AI model configurations:

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `ABI_DEFAULT_MODEL` | Default LLM model | `"gpt-4"` | `"gpt-4"`, `"gpt-3.5-turbo"`, etc. |
| `ABI_MODEL_TIMEOUT` | Model request timeout (seconds) | `60` | Integer value |
| `ABI_MODEL_TEMPERATURE` | Default temperature parameter | `0.7` | Float value between 0 and 2 |
| `ABI_MODEL_MAX_TOKENS` | Maximum response tokens | `1000` | Integer value |
| `ABI_OPENAI_API_KEY` | OpenAI API key | | Required for OpenAI models |
| `ABI_ANTHROPIC_API_KEY` | Anthropic API key | | Required for Anthropic models |
| `ABI_LOCAL_MODEL_PATH` | Path to local models | `"./models"` | File path |

## Storage and File Variables

These variables control file storage:

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `ABI_STORAGE_TYPE` | Storage backend type | `"local"` | `"local"`, `"s3"`, `"azure"`, `"gcs"` |
| `ABI_STORAGE_PATH` | Local storage path | `"./storage"` | File path |
| `ABI_S3_BUCKET` | S3 bucket name | | Required for S3 storage |
| `ABI_S3_REGION` | S3 region | | Required for S3 storage |
| `ABI_S3_ACCESS_KEY` | S3 access key | | Required for S3 storage |
| `ABI_S3_SECRET_KEY` | S3 secret key | | Required for S3 storage |
| `ABI_MAX_UPLOAD_SIZE` | Maximum upload size (MB) | `50` | Integer value |
| `ABI_ALLOWED_EXTENSIONS` | Allowed file extensions | `".pdf,.txt,.csv,.json"` | Comma-separated list |

## Monitoring and Logging Variables

These variables control monitoring and logging:

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `ABI_LOG_FORMAT` | Log output format | `"standard"` | `"standard"`, `"json"` |
| `ABI_LOG_FILE` | Log file path | `""` | File path |
| `ABI_LOG_ROTATION` | Enable log rotation | `"true"` | `"true"`, `"false"` |
| `ABI_LOG_MAX_SIZE` | Maximum log file size (MB) | `100` | Integer value |
| `ABI_LOG_BACKUP_COUNT` | Number of log backups to keep | `10` | Integer value |
| `ABI_ENABLE_ACCESS_LOGS` | Enable API access logs | `"true"` | `"true"`, `"false"` |
| `ABI_ENABLE_METRICS` | Enable Prometheus metrics | `"true"` | `"true"`, `"false"` |
| `ABI_METRICS_PORT` | Prometheus metrics port | `9090` | Integer value |
| `ABI_SENTRY_DSN` | Sentry DSN for error tracking | `""` | DSN URL |
| `ABI_TRACE_ENABLED` | Enable distributed tracing | `"false"` | `"true"`, `"false"` |
| `ABI_TRACE_SAMPLE_RATE` | Tracing sample rate | `0.1` | Float value between 0 and 1 |

## Environment-Specific Recommendations

### Development Environment

For local development, use a `.env` file with these settings:

```
ABI_ENVIRONMENT=development
ABI_LOG_LEVEL=DEBUG
ABI_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/abi_dev
ABI_ONTOLOGY_ENDPOINT=http://localhost:3030/abi/sparql
ABI_REDIS_URL=redis://localhost:6379/0
ABI_SECRET_KEY=your-dev-secret-key-replace-in-production
ABI_AUTH_ENABLED=false
ABI_ENABLE_CORS=true
ABI_CORS_ORIGINS=http://localhost:3000,http://localhost:8080
ABI_DATABASE_ECHO=true
```

### Staging Environment

For staging environments, use:

```
ABI_ENVIRONMENT=staging
ABI_LOG_LEVEL=INFO
ABI_DATABASE_URL=postgresql://abi_user:password@db.staging.example.com:5432/abi_staging
ABI_ONTOLOGY_ENDPOINT=http://triplestore.staging.example.com:3030/abi/sparql
ABI_REDIS_URL=redis://cache.staging.example.com:6379/0
ABI_SECRET_KEY=randomly-generated-secret-key
ABI_AUTH_ENABLED=true
ABI_JWT_EXPIRATION=3600
ABI_ENABLE_METRICS=true
ABI_ENABLE_CORS=true
ABI_CORS_ORIGINS=https://app.staging.example.com
```

### Production Environment

For production environments, use:

```
ABI_ENVIRONMENT=production
ABI_LOG_LEVEL=WARNING
ABI_DATABASE_URL=postgresql://abi_user:strong-password@db.example.com:5432/abi_production
ABI_ONTOLOGY_ENDPOINT=http://triplestore.example.com:3030/abi/sparql
ABI_REDIS_URL=redis://cache.example.com:6379/0
ABI_SECRET_KEY=very-long-randomly-generated-key
ABI_AUTH_ENABLED=true
ABI_JWT_EXPIRATION=1800
ABI_PASSWORD_COMPLEXITY=high
ABI_MFA_ENABLED=true
ABI_DATABASE_SSL_MODE=require
ABI_ENABLE_METRICS=true
ABI_RATE_LIMIT_ENABLED=true
ABI_SENTRY_DSN=https://your-sentry-dsn
ABI_LOG_FORMAT=json
```

## Setting Environment Variables

### Linux/macOS

```bash
# Set a single variable
export ABI_SECRET_KEY="your-secret-key"

# Set multiple variables from a file
set -a
source .env
set +a
```

### Windows

```cmd
# Set a single variable
set ABI_SECRET_KEY=your-secret-key

# Or using PowerShell
$env:ABI_SECRET_KEY = "your-secret-key"
```

### Docker

```bash
# In docker-compose.yml
services:
  abi:
    image: abi:latest
    environment:
      - ABI_ENVIRONMENT=production
      - ABI_DATABASE_URL=postgresql://user:pass@db:5432/abi
      # Additional variables...
```

### Kubernetes

```yaml
# As environment variables in deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: abi-api
spec:
  template:
    spec:
      containers:
      - name: abi-api
        env:
        - name: ABI_ENVIRONMENT
          value: "production"
        - name: ABI_API_PORT
          value: "8000"
        # Additional variables...

# Using ConfigMaps
apiVersion: v1
kind: ConfigMap
metadata:
  name: abi-config
data:
  ABI_ENVIRONMENT: "production"
  ABI_LOG_LEVEL: "WARNING"
  # Additional non-sensitive variables...

# Using Secrets for sensitive values
apiVersion: v1
kind: Secret
metadata:
  name: abi-secrets
type: Opaque
data:
  ABI_SECRET_KEY: <base64-encoded-value>
  ABI_DATABASE_URL: <base64-encoded-value>
  # Additional sensitive variables...
```

## Best Practices

1. **Never commit sensitive environment variables** to version control
2. **Use different values for different environments**
3. **Document all environment variables** used by your application
4. **Validate environment variables** at application startup
5. **Use a secret management service** in production
6. **Rotate sensitive values** periodically
7. **Limit access** to production environment variables
8. **Use a `.env.example` file** with dummy values as a template

## Environment Variable Validation

ABI validates environment variables at startup:

```python
import os
from pydantic import BaseSettings, validator

class Settings(BaseSettings):
    # Define variables with types and defaults
    ABI_ENVIRONMENT: str = "development"
    ABI_LOG_LEVEL: str = "INFO"
    ABI_DATABASE_URL: str
    
    # Validators
    @validator("ABI_LOG_LEVEL")
    def valid_log_level(cls, v):
        if v not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid log level: {v}")
        return v
    
    @validator("ABI_DATABASE_URL")
    def valid_database_url(cls, v):
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("Database URL must be a PostgreSQL connection string")
        return v

# Load and validate settings
settings = Settings()
```

## Troubleshooting

### Common Issues

1. **Missing Required Variables**
   - Error: `ValueError: ABI_SECRET_KEY is not set`
   - Solution: Set the required environment variable

2. **Invalid Database URL**
   - Error: `ValueError: Database URL must be a PostgreSQL connection string`
   - Solution: Check the format of your database URL

3. **Environment Variables Not Recognized**
   - Issue: Variables are set but not recognized by the application
   - Solution: Ensure variables are available in the application's environment
   
4. **Docker Environment Variables Not Applied**
   - Issue: Variables set in Docker are not available to the application
   - Solution: Check the Docker command or docker-compose.yml file

5. **Kubernetes Secrets Not Available**
   - Issue: Secrets are not available in the pod
   - Solution: Check the Secret object and the pod's spec for correct mounting

## Additional Resources

- [12-Factor App: Config](https://12factor.net/config) - Best practices for app configuration
- [Docker Environment Variables](https://docs.docker.com/compose/environment-variables/)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Managing Environment Variables (Python)](https://docs.python.org/3/library/os.html#os.environ)
- [Pydantic Settings Management](https://pydantic-docs.helpmanual.io/usage/settings/) 