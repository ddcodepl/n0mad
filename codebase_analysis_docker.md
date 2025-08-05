# Nomad Codebase Analysis for Dockerization

## Project Overview
**Nomad** is a Notion API integration application for task refinement and automation with AI integration. It's built in Python 3.11 and integrates with various AI providers (OpenAI, Anthropic Claude, OpenRouter) and Slack.

## Application Architecture

### Core Components
- **Entry Point**: `entry/main.py` - Combined main application supporting multiple processing modes
- **Core Services**: 
  - `core/managers/` - Status transition, feedback, notification managers
  - `core/processors/` - Content processing (simple, multi-queue, multi-status)
  - `core/operations/` - Database operations, command execution
  - `core/services/` - Git, Slack, task validation services
- **Client Integrations**: 
  - `clients/notion_wrapper.py` - Notion API client
  - `clients/openai_client.py` - OpenAI API client  
  - `clients/claude_engine_invoker.py` - Claude API client
  - `clients/openrouter_client.py` - OpenRouter API client
- **Utilities**: Configuration, logging, performance monitoring, security validation

### Processing Modes
1. **Refine Mode** (`--refine`) - Process tasks with 'To Refine' status
2. **Prepare Mode** (`--prepare`) - Process tasks with 'Prepare Tasks' status  
3. **Queued Mode** (`--queued`) - Process tasks with 'Queued to run' status
4. **Multi Mode** (`--multi`) - Multi-status processing
5. **Continuous Polling** (default) - Continuous monitoring across all statuses

### Python Dependencies Analysis

#### Core Dependencies (requirements.txt)
```
psutil>=7.0.0           # System monitoring
notion-client>=2.2.1    # Notion API integration
openai>=1.35.0         # OpenAI API
python-dotenv>=1.0.1   # Environment variables
aiohttp>=3.9.0         # Async HTTP client
pytest>=7.0.0          # Testing framework
setuptools>=65.0.0     # Package management
pydantic>=2.0.0        # Data validation
requests>=2.28.0       # HTTP requests
slack-sdk>=3.25.0      # Slack integration
```

#### Python Version Compatibility
- **Target**: Python 3.11 (specified in tasks)
- **Current Support**: Python 3.8+ (pyproject.toml specifies >=3.8.1)
- **Classifiers**: Support for 3.9, 3.10, 3.11, 3.12

### Node.js Components
- **Package**: `nomad-task-processor` (package.json)
- **Main Script**: `process-tasks.js` 
- **Dependencies**:
  - `axios@^1.4.0` - HTTP client
  - `fs-extra@^11.0.0` - File system utilities
  - `dotenv@^16.0.0` - Environment variable loading

### Configuration Requirements

#### Required Environment Variables
- `NOTION_TOKEN` - Notion API token
- `NOTION_BOARD_DB` - Notion database ID
- AI Provider Keys (at least one required):
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY` 
  - `OPENROUTER_API_KEY`

#### Optional Environment Variables
- `NOMAD_MAX_CONCURRENT_TASKS` - Concurrent task limit (default: 3)
- `NOMAD_CONFIG_FILE` - Global config file path
- `TASKS_DIR` - Task files directory
- Slack integration variables
- Performance monitoring settings

### File System Structure
```
nomad/
├── entry/main.py              # Application entry point
├── core/                      # Core application logic
│   ├── managers/             # Business logic managers
│   ├── processors/           # Task processors
│   ├── operations/           # Database & command operations
│   └── services/             # External service integrations
├── clients/                  # API client wrappers
├── utils/                    # Utility modules
├── tests/                    # Test suite
├── logs/                     # Application logs
├── tasks/                    # Task storage (pre-refined, refined, summary)
├── data/                     # Data files
├── scripts/                  # Utility scripts
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Python project configuration
├── package.json             # Node.js dependencies
└── process-tasks.js         # Node.js task processor
```

### External Service Dependencies
1. **Notion API** - Primary data source
2. **AI Providers** - Content processing (OpenAI, Anthropic, OpenRouter)
3. **Slack API** - Notifications (optional)
4. **File System** - Local task storage and processing

### Network Requirements
- **Outbound HTTPS** to:
  - api.notion.com (Notion API)
  - api.openai.com (OpenAI API)
  - api.anthropic.com (Claude API)
  - openrouter.ai (OpenRouter API)
  - slack.com (Slack API)

### Docker Considerations

#### Base Image Recommendations
- **Python 3.11-slim** or **Python 3.11-alpine** for minimal footprint
- Need Node.js for process-tasks.js component

#### Multi-stage Build Strategy
1. **Stage 1**: Install Node.js dependencies and build/prepare JS components
2. **Stage 2**: Install Python dependencies and application code
3. **Stage 3**: Runtime stage with both Python 3.11 and Node.js runtime

#### Port Configuration
- Application appears to be CLI-based, no web server detected
- May need ports for:
  - Health checks (custom port)
  - Monitoring/metrics endpoints
  - Inter-service communication if deployed in microservices

#### Volume Mounts Needed
- `/app/logs` - Application logs
- `/app/tasks` - Task storage
- `/app/data` - Data files
- Configuration files

#### Environment Variable Strategy
- Use Docker secrets for API keys
- Environment-specific configuration via ConfigMaps
- Global configuration file mounting

#### Health Check Strategy
- Implement health check endpoint or CLI command
- Check Notion API connectivity
- Validate AI provider API keys
- Monitor task processing queues

## Security Considerations
- All API keys must be handled as secrets
- File system permissions for task storage
- Network policies for external API access
- Security validation utilities already present in codebase

## Deployment Patterns
- **Standalone Container**: Single container with all components
- **Sidecar Pattern**: Separate containers for Python app and Node.js processor
- **Job/CronJob Pattern**: Kubernetes Jobs for scheduled processing
- **Continuous Deployment**: Long-running container for continuous polling mode

## Performance Considerations
- Concurrent task processing (configurable limit)
- Performance monitoring utilities already integrated
- Memory usage monitoring via psutil
- Async HTTP operations via aiohttp

## Integration Points for Docker
1. **Configuration Management**: Environment variables and config file mounting
2. **Logging**: Structured logging to stdout/stderr for container logs
3. **Health Monitoring**: Health check endpoints for container orchestration
4. **Graceful Shutdown**: Signal handling for clean container termination
5. **Data Persistence**: Volume mounts for task storage and logs