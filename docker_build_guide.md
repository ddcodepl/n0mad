# Docker Build and Configuration Guide

## Docker Image Overview

The Nomad application has been successfully containerized using a multi-stage Docker build strategy that supports both Python 3.11 and Node.js components.

### Image Details
- **Base Image**: Python 3.11-slim with Node.js 20
- **Image Size**: ~638MB (optimized multi-stage build)
- **Architecture**: Supports ARM64 and AMD64
- **Security**: Non-root user (appuser:1000)
- **Health Check**: Built-in health monitoring

## Build Configuration

### Multi-Stage Build Process

#### Stage 1: Node.js Builder (`node-builder`)
```dockerfile
FROM node:20-alpine as node-builder
# Installs Node.js dependencies for process-tasks.js
# Uses Alpine for minimal footprint
# Includes: axios, fs-extra, dotenv
```

#### Stage 2: Python Builder (`python-builder`)
```dockerfile
FROM python:3.11-slim as python-builder  
# Installs Python dependencies and application
# Creates virtual environment at /opt/venv
# Installs all requirements.txt dependencies
```

#### Stage 3: Runtime (`runtime`)
```dockerfile
FROM python:3.11-slim as runtime
# Combines Python 3.11 + Node.js 20 runtime
# Copies virtual environment and Node.js components
# Sets up non-root user for security
```

## Build Commands

### Basic Build
```bash
# Build the image
docker build -t nomad:latest .

# Build with specific tag
docker build -t nomad:v0.2.0 .

# Build for multiple architectures (if using buildx)
docker buildx build --platform linux/amd64,linux/arm64 -t nomad:latest .
```

### Development Build
```bash
# Build development version with build args
docker build \
  --build-arg PYTHON_VERSION=3.11 \
  --build-arg NODE_VERSION=20 \
  -t nomad:dev .
```

## Image Testing

### Verify Installation
```bash
# Test Python version
docker run --rm nomad:latest python3 --version
# Expected: Python 3.11.13

# Test Node.js version  
docker run --rm nomad:latest node --version
# Expected: v20.19.4

# Test application imports
docker run --rm nomad:latest python3 -c "import entry.main; print('OK')"
# Expected: Configuration logs + "OK"
```

### Health Check Testing
```bash
# Run health check manually
docker run --rm nomad:latest /app/healthcheck.sh

# View health status of running container
docker inspect --format='{{json .State.Health}}' <container_id>
```

## Runtime Configuration

### Environment Variables Required
```bash
# Core Notion Integration
NOTION_TOKEN=secret_xxxxxxxxxxxx
NOTION_BOARD_DB=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# AI Provider (at least one required)
OPENAI_API_KEY=sk-xxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx  
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxx

# Optional Configuration
NOMAD_MAX_CONCURRENT_TASKS=3
NOMAD_CONFIG_FILE=/app/config/nomad.conf
TASKS_DIR=/app/tasks
```

### Volume Mounts
```bash
# Persistent storage locations
/app/logs          # Application logs
/app/tasks         # Task storage and processing
/app/data          # Data files
/app/.taskmaster   # TaskMaster configuration
```

## Running the Container

### Basic Execution Modes

#### Continuous Polling (Default)
```bash
docker run -d \
  --name nomad-app \
  -e NOTION_TOKEN=secret_xxx \
  -e NOTION_BOARD_DB=xxx \
  -e OPENAI_API_KEY=sk-xxx \
  -v nomad-logs:/app/logs \
  -v nomad-tasks:/app/tasks \
  nomad:latest
```

#### Specific Processing Modes
```bash
# Refine mode
docker run --rm \
  --env-file .env \
  nomad:latest python3 -m entry.main --refine

# Prepare mode  
docker run --rm \
  --env-file .env \
  nomad:latest python3 -m entry.main --prepare

# Queued mode
docker run --rm \
  --env-file .env \
  nomad:latest python3 -m entry.main --queued

# Multi-status mode
docker run --rm \
  --env-file .env \
  nomad:latest python3 -m entry.main --multi
```

### Health Monitoring
```bash
# Check container health
docker run -d \
  --name nomad-app \
  --env-file .env \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  nomad:latest

# Monitor health status
docker logs nomad-app
docker inspect nomad-app | grep -A 5 "Health"
```

## Security Configuration

### Non-Root Execution
- Container runs as `appuser:appuser` (UID:GID 1000:1000)
- All application files owned by appuser
- No privileged operations required

### Network Security
- Exposes port 8080 for health checks only
- Outbound HTTPS connections to:
  - api.notion.com
  - api.openai.com  
  - api.anthropic.com
  - openrouter.ai
  - slack.com (optional)

### Secrets Management
```bash
# Using Docker secrets (recommended for production)
echo "secret_notion_token" | docker secret create notion_token -
echo "sk-openai_key" | docker secret create openai_key -

docker service create \
  --name nomad-service \
  --secret notion_token \
  --secret openai_key \
  nomad:latest
```

## Performance Optimization

### Image Size Optimization
- Multi-stage build reduces final image size
- .dockerignore excludes unnecessary files
- Alpine base for Node.js builder stage
- Slim Python base for minimal runtime

### Runtime Performance
- Python virtual environment for dependency isolation
- Concurrent task processing (configurable)
- Health check monitoring
- Graceful shutdown handling

### Resource Limits
```bash
# Production resource limits
docker run -d \
  --name nomad-app \
  --memory=512m \
  --memory-swap=1g \
  --cpus="1.0" \
  --env-file .env \
  nomad:latest
```

## Troubleshooting

### Common Issues

#### Build Failures
```bash
# Clear Docker cache if build fails
docker builder prune -f

# Check build logs
docker build --no-cache --progress=plain -t nomad:debug .
```

#### Runtime Issues  
```bash
# Check container logs
docker logs nomad-app

# Interactive debugging
docker run -it --rm \
  --env-file .env \
  nomad:latest /bin/bash

# Test configurations
docker run --rm \
  --env-file .env \
  nomad:latest python3 -m entry.main --config-status
```

#### Permission Issues
```bash
# Fix volume permissions
docker run --rm -v nomad-logs:/app/logs \
  nomad:latest chown -R appuser:appuser /app/logs
```

### Health Check Debugging
```bash
# Manual health check
docker exec nomad-app /app/healthcheck.sh

# Check health check logs
docker inspect nomad-app --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

## Production Deployment

### Docker Compose (Next Task)
- See docker-compose.yml for complete stack
- Includes environment management
- Volume persistence
- Service networking

### Kubernetes Deployment
```yaml
# Example deployment snippet
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nomad
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nomad
  template:
    metadata:
      labels:
        app: nomad
    spec:
      containers:
      - name: nomad
        image: nomad:latest
        env:
        - name: NOTION_TOKEN
          valueFrom:
            secretKeyRef:
              name: nomad-secrets
              key: notion-token
        volumeMounts:
        - name: logs
          mountPath: /app/logs
        - name: tasks  
          mountPath: /app/tasks
        livenessProbe:
          exec:
            command: ["/app/healthcheck.sh"]
          initialDelaySeconds: 10
          periodSeconds: 30
```

## Build Verification Checklist

✅ **Build Success**: Image builds without errors  
✅ **Python 3.11**: Correct Python version installed  
✅ **Node.js 20**: Node.js runtime available for process-tasks.js  
✅ **Dependencies**: All Python and Node.js packages installed  
✅ **Security**: Non-root user configuration  
✅ **Health Check**: Health monitoring functional  
✅ **Entry Points**: Application imports and runs correctly  
✅ **Size Optimization**: Multi-stage build minimizes image size

## Next Steps

1. **Environment Configuration** (Task 234)
2. **Docker Compose Setup** (Task 235) 
3. **Service Integration** (Task 236)
4. **Network Configuration** (Task 237)
5. **Production Optimization** (Task 238)