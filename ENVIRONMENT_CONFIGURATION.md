# Environment Configuration and Secrets Management

## Overview

This document describes the complete environment variable configuration and secrets management strategy for the Nomad application in Docker deployments.

## Quick Start

1. **Copy the environment template**:
   ```bash
   cp .env.example .env
   ```

2. **Fill in your values** (see [Required Variables](#required-variables))

3. **Validate configuration**:
   ```bash
   python3 scripts/validate_environment.py
   ```

4. **Test with Docker**:
   ```bash
   docker run --rm --env-file .env nomad:latest python3 -m entry.main --config-status
   ```

## Required Variables

### Notion Integration
| Variable | Format | Description | Example |
|----------|--------|-------------|---------|
| `NOTION_TOKEN` | `secret_*` | Notion API integration token | `secret_abc123...` |
| `NOTION_BOARD_DB` | UUID format | Notion database ID | `12345678-1234-5678-9abc-123456789abc` |

**How to get these values**:
- **NOTION_TOKEN**: Create integration at https://www.notion.so/my-integrations
- **NOTION_BOARD_DB**: Extract from your Notion database URL

### AI Provider (At least ONE required)
| Variable | Format | Description | Priority |
|----------|--------|-------------|----------|
| `OPENAI_API_KEY` | `sk-*` | OpenAI API key for GPT models | High |
| `ANTHROPIC_API_KEY` | `sk-ant-*` | Anthropic API key for Claude models | High |
| `OPENROUTER_API_KEY` | `sk-or-*` | OpenRouter API key (multiple models) | Medium |

## Optional Variables

### Application Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `NOMAD_HOME` | `/app/.nomad` | Base directory for Nomad files |
| `NOMAD_TASKS_DIR` | `/app/tasks` | Directory for task files |
| `NOMAD_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `NOMAD_MAX_CONCURRENT_TASKS` | `3` | Maximum concurrent task processing |
| `NOMAD_CONFIG_FILE` | `/app/config/nomad.conf` | Additional configuration file path |

### Task Processing Configuration  
| Variable | Default | Description |
|----------|---------|-------------|
| `NOMAD_COMMIT_VALIDATION_ENABLED` | `true` | Enable checkbox validation for status transitions |
| `NOMAD_COMMIT_CHECKBOX_NAME` | `Commit` | Name of commit checkbox property in Notion |
| `NOMAD_VALIDATION_CACHE_TTL_MINUTES` | `5` | Cache TTL for validations (minutes) |
| `NOMAD_VALIDATION_STRICT_MODE` | `false` | Fail transitions if checkbox not found |

### Slack Integration (Optional)
| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | - | Slack bot token (`xoxb-*`) |
| `SLACK_APP_TOKEN` | - | Slack app token (`xapp-*`) |
| `SLACK_DEFAULT_CHANNEL` | `#general` | Default notification channel |
| `SLACK_ERROR_CHANNEL` | `#errors` | Error notification channel |
| `SLACK_NOTIFICATIONS_ENABLED` | `true` | Enable Slack notifications |
| `SLACK_RATE_LIMIT_PER_MINUTE` | `60` | Messages per minute limit |
| `SLACK_RETRY_ATTEMPTS` | `3` | Retry attempts for failed messages |
| `SLACK_RETRY_DELAY` | `5` | Delay between retries (seconds) |
| `SLACK_TIMEOUT` | `30` | Request timeout (seconds) |

### Docker-Specific Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `NOMAD_DOCKER_ENV` | `1` | Container environment indicator |
| `PYTHONDONTWRITEBYTECODE` | `1` | Don't create .pyc files |
| `PYTHONUNBUFFERED` | `1` | Unbuffered stdout/stderr |
| `PYTHONPATH` | `/app` | Python module search path |

## Secrets Management

### Development Environment
For development, use `.env` files:

```bash
# Copy template
cp .env.example .env

# Edit with your values
nano .env

# Load automatically with docker-compose
docker-compose up
```

### Production Deployment

#### Docker Swarm Secrets
```bash
# Create secrets
echo "secret_your_token" | docker secret create notion_token -
echo "your_database_id" | docker secret create notion_board_db -
echo "sk-your_key" | docker secret create openai_api_key -

# Deploy with secrets
docker stack deploy -c docker-compose.prod.yml nomad
```

#### Kubernetes Secrets
```bash
# Create secret
kubectl create secret generic nomad-secrets \
  --from-literal=notion-token="secret_your_token" \
  --from-literal=notion-board-db="your_database_id" \
  --from-literal=openai-api-key="sk-your_key"

# Deploy
kubectl apply -f kubernetes-deployment.yaml
```

#### HashiCorp Vault Integration
```bash
# Store in Vault
vault kv put secret/nomad \
  notion_token="secret_your_token" \
  notion_board_db="your_database_id" \
  openai_api_key="sk-your_key"

# Use with agent injection or CSI driver
```

## Security Best Practices

### 1. Secret Rotation
- **Frequency**: Rotate API keys every 90 days
- **Process**: Update secrets in secret store, restart services
- **Monitoring**: Monitor for authentication failures after rotation

### 2. Access Control
- **Principle of Least Privilege**: Only grant necessary permissions
- **Service Accounts**: Use dedicated service accounts for each environment
- **Network Policies**: Restrict network access to required services only

### 3. Secret Storage
- **Never commit** real secrets to version control
- **Use encrypted storage** for secrets at rest
- **Limit access** to secrets to essential personnel only
- **Audit access** to secrets regularly

### 4. Environment Separation
```bash
# Development
NOMAD_ENV=development
NOMAD_LOG_LEVEL=DEBUG

# Production  
NOMAD_ENV=production
NOMAD_LOG_LEVEL=INFO
NOMAD_COMMIT_VALIDATION_ENABLED=true
```

## Validation and Testing

### Environment Validation Script
```bash
# Basic validation
python3 scripts/validate_environment.py

# Strict validation (exits with error if issues found)
python3 scripts/validate_environment.py --strict

# Validate specific environment file
python3 scripts/validate_environment.py --env-file .env.production
```

### Application Configuration Test
```bash
# Test configuration loading
docker run --rm --env-file .env nomad:latest \
  python3 -m entry.main --config-status

# Test health check
docker run --rm --env-file .env nomad:latest \
  /app/healthcheck.sh
```

### Integration Testing
```bash
# Test Notion connectivity
docker run --rm --env-file .env nomad:latest \
  python3 -c "from clients.notion_wrapper import NotionClientWrapper; \
               client = NotionClientWrapper(); \
               print('Notion OK' if client.test_connection() else 'Notion FAIL')"

# Test AI provider connectivity  
docker run --rm --env-file .env nomad:latest \
  python3 -c "from clients.openai_client import OpenAIClient; \
               client = OpenAIClient(); \
               print('AI Provider OK')"
```

## Environment File Examples

### Development (.env.development)
```bash
# Development environment
NOMAD_ENV=development
NOMAD_LOG_LEVEL=DEBUG
NOMAD_MAX_CONCURRENT_TASKS=1

# Required
NOTION_TOKEN=secret_dev_token_here
NOTION_BOARD_DB=dev_database_id_here
OPENAI_API_KEY=sk-dev_openai_key_here

# Slack (optional for dev)
SLACK_NOTIFICATIONS_ENABLED=false
```

### Staging (.env.staging)
```bash
# Staging environment
NOMAD_ENV=staging  
NOMAD_LOG_LEVEL=INFO
NOMAD_MAX_CONCURRENT_TASKS=2

# Required
NOTION_TOKEN=secret_staging_token_here
NOTION_BOARD_DB=staging_database_id_here
OPENAI_API_KEY=sk-staging_openai_key_here

# Slack notifications enabled
SLACK_NOTIFICATIONS_ENABLED=true
SLACK_BOT_TOKEN=xoxb-staging-token
SLACK_DEFAULT_CHANNEL=#staging-notifications
```

### Production (.env.production)
```bash
# Production environment
NOMAD_ENV=production
NOMAD_LOG_LEVEL=INFO
NOMAD_MAX_CONCURRENT_TASKS=3
NOMAD_COMMIT_VALIDATION_ENABLED=true
NOMAD_VALIDATION_STRICT_MODE=true

# Required (use secrets in production)
NOTION_TOKEN_FILE=/run/secrets/notion_token
NOTION_BOARD_DB_FILE=/run/secrets/notion_board_db
OPENAI_API_KEY_FILE=/run/secrets/openai_api_key

# Slack production notifications
SLACK_NOTIFICATIONS_ENABLED=true
SLACK_BOT_TOKEN_FILE=/run/secrets/slack_bot_token
SLACK_DEFAULT_CHANNEL=#production-notifications
SLACK_ERROR_CHANNEL=#production-alerts
```

## Troubleshooting

### Common Issues

#### Missing Required Variables
```bash
Error: Required environment variables not set: NOTION_TOKEN, NOTION_BOARD_DB
```
**Solution**: Ensure all required variables are set in your environment or `.env` file.

#### Invalid API Key Format
```bash
Warning: OPENAI_API_KEY format issues: Key should start with 'sk-'
```
**Solution**: Verify API key format matches provider requirements.

#### Permission Denied for Directories
```bash
Error: Cannot create directory: /app/tasks
```
**Solution**: Ensure proper volume mounts and container permissions.

#### Slack Configuration Issues
```bash
Warning: Slack notifications enabled but SLACK_BOT_TOKEN not configured
```
**Solution**: Either disable Slack notifications or provide valid bot token.

### Debugging Commands

```bash
# Check environment variables in container
docker run --rm --env-file .env nomad:latest env | grep NOMAD

# Test configuration loading
docker run --rm --env-file .env nomad:latest \
  python3 -c "from utils.global_config import initialize_global_config; \
               config = initialize_global_config(); \
               print('Config loaded successfully')"

# Validate specific components
docker run --rm --env-file .env nomad:latest \
  python3 -m entry.main --health-check
```

## Migration Guide

### From Local Development to Docker

1. **Create .env file** from existing environment variables
2. **Update file paths** to container paths (`/app/...`)
3. **Set Docker environment indicator**: `NOMAD_DOCKER_ENV=1`
4. **Test configuration** with validation script

### From Docker Compose to Kubernetes

1. **Create Kubernetes secrets** from environment variables
2. **Update deployment** to reference secrets
3. **Configure persistent volumes** for data directories
4. **Set up ingress/services** for external access

### From Development to Production

1. **Use external secret management** (Vault, K8s secrets, etc.)
2. **Enable strict validation**: `NOMAD_VALIDATION_STRICT_MODE=true`
3. **Configure monitoring** and alerting
4. **Set appropriate resource limits**
5. **Enable health checks** and liveness probes

## Additional Resources

- **Notion API Documentation**: https://developers.notion.com/
- **OpenAI API Documentation**: https://platform.openai.com/docs/
- **Docker Secrets**: https://docs.docker.com/engine/swarm/secrets/
- **Kubernetes Secrets**: https://kubernetes.io/docs/concepts/configuration/secret/
- **Environment Security Best Practices**: https://12factor.net/config