# Managing Production Secrets

This guide covers how to securely manage secrets for production deployments using the ABI CLI and NAAS secret management system.

## Overview

The ABI platform supports multiple secret management approaches with a clear priority order:

1. **Environment Variables** (highest priority)
2. **Local .env files** (`.env`, `.env.prod`)
3. **NAAS Secrets** (centralized secret store, lowest priority)

Secrets are automatically loaded from NAAS and local files into environment variables at runtime, ensuring seamless access across your application.

## TL;DR

### Retrieve Secrets from Production
```bash
# Get current production secrets
./cli secrets naas get-base64-env --naas-api-key='your_naas_api_key' > .env.prod
```

### Push New Secrets to Production
```bash
# 1. Update your .env.prod file with new secrets
# 2. Push to NAAS (⚠️ Use with caution - this overwrites existing secrets)
./cli secrets naas push-env-as-base64 --naas-api-key='your_naas_api_key'
```

## Environment File Format

Your `.env.prod` file should follow standard environment variable format:

```bash
# Core Configuration
ENV=prod
AI_MODE=cloud

# API Keys - AI Services
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
PERPLEXITY_API_KEY=pplx-...
MISTRAL_API_KEY=...
XAI_API_KEY=xai-...
GOOGLE_API_KEY=AIza...

# Integration Credentials
GITHUB_ACCESS_TOKEN=ghp_...
NAAS_API_KEY=eyJ...
TELEGRAM_BOT_KEY=...

# LinkedIn Cookies (for LinkedIn integration)
li_at=AQE...
JSESSIONID=ajax:...

# Cloud Services
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-west-2

# Database Configuration (if using AWS Neptune)
AWS_NEPTUNE_DB_INSTANCE_IDENTIFIER=db-neptune-1-instance-1
AWS_BASTION_HOST=...
AWS_BASTION_PORT=22
AWS_BASTION_USER=ec2-user
AWS_BASTION_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----

# Application Settings
LOG_LEVEL=DEBUG
ABI_API_KEY=your_api_key
```

## Security Best Practices

### 🔒 Secret Management
- **Never commit secrets to git**: Ensure `.env*` files are in `.gitignore`
- **Use environment-specific files**: Separate `.env.dev`, `.env.staging`, `.env.prod`
- **Rotate keys regularly**: Update API keys and tokens periodically
- **Limit permissions**: Use least-privilege principle for service accounts

### 🛡️ NAAS API Key Security
- Store your NAAS API key as an environment variable: `export NAAS_API_KEY='your_key'`
- Use `--naas-api-key=$NAAS_API_KEY` instead of hardcoding in commands
- Consider using a secrets management tool for CI/CD pipelines

### ⚠️ Production Deployment
- **Backup before changes**: Always retrieve current secrets before pushing updates
- **Test in staging**: Validate secret changes in non-production environments first
- **Monitor deployments**: Check application logs after secret updates
- **Rollback plan**: Keep previous secret versions for quick recovery