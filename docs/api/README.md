# Nomad API Documentation

Welcome to the comprehensive API documentation for Nomad. This section covers all APIs, interfaces, and integration points available in the Nomad ecosystem.

## Overview

Nomad provides several types of APIs and interfaces:

1. **Internal Python APIs** - Core classes and methods for extending Nomad
2. **Integration APIs** - Interfaces for external service integration
3. **Command Line Interface** - CLI commands and parameters
4. **Configuration APIs** - Configuration management interfaces
5. **Plugin Interfaces** - Extension and customization points

## API Categories

### 🔌 [Integration APIs](integration-apis.md)
External service integrations and their APIs:
- [Notion API Integration](notion-api.md)
- [AI Provider APIs](ai-provider-apis.md)
- [Slack API Integration](slack-api.md)
- [Git Integration APIs](git-api.md)

### 🐍 [Internal Python APIs](internal-apis.md)
Core Python classes and methods:
- [Client APIs](clients/)
- [Core Services](services/)
- [Processors](processors/)
- [Managers](managers/)
- [Utilities](utilities/)

### 💻 [Command Line Interface](cli-api.md)
Complete CLI reference:
- Commands and options
- Configuration parameters
- Exit codes and return values

### ⚙️ [Configuration APIs](configuration-api.md)
Configuration management interfaces:
- Environment variables
- Configuration files
- Dynamic configuration

### 🔧 [Plugin Interfaces](plugin-interfaces.md)
Extension and customization points:
- Custom processors
- Integration plugins
- Notification handlers

## Quick Start

### Basic API Usage

```python
from nomad.clients import NotionClientWrapper, OpenAIClient
from nomad.core.processors import ContentProcessor

# Initialize clients
notion = NotionClientWrapper()
openai = OpenAIClient()

# Create processor
processor = ContentProcessor(notion, openai)

# Process a task
result = processor.process_task(task_data)
```

### CLI Usage

```bash
# Basic commands
nomad --version
nomad --help
nomad --config-status

# Processing modes
nomad --refine     # Process "To Refine" tasks
nomad --prepare    # Process "Prepare Tasks"
nomad --queued     # Process "Queued to run" tasks
```

## Authentication

Most APIs require authentication through environment variables:

```env
# Required for Notion integration
NOTION_TOKEN=secret_your_notion_token
NOTION_BOARD_DB=your_database_id

# Required for AI processing (at least one)
OPENAI_API_KEY=sk-your_openai_key
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key
OPENROUTER_API_KEY=sk-or-your_openrouter_key

# Optional for Slack integration
SLACK_BOT_TOKEN=xoxb-your_slack_token
```

## Error Handling

All APIs use consistent error handling patterns:

```python
from nomad.core.exceptions import NomadError, APIError, ConfigurationError

try:
    result = api_call()
except APIError as e:
    print(f"API Error: {e.message}")
    print(f"Error Code: {e.code}")
except ConfigurationError as e:
    print(f"Configuration Error: {e.message}")
except NomadError as e:
    print(f"General Error: {e.message}")
```

## Response Formats

### Standard Response Format

Most APIs return responses in this format:

```python
{
    "status": "success|error",
    "data": {
        # Response data
    },
    "meta": {
        "timestamp": "2024-01-01T00:00:00Z",
        "request_id": "req_12345",
        "version": "0.2.0"
    },
    "error": {  # Only present on error
        "code": "ERROR_CODE",
        "message": "Human readable error message",
        "details": {}
    }
}
```

### Task Processing Response

```python
{
    "status": "completed|failed|aborted|skipped",
    "task_id": "TASK-123",
    "page_id": "notion_page_id",
    "message": "Processing completed successfully",
    "data": {
        "original_content": "...",
        "processed_content": "...",
        "changes_made": ["change1", "change2"]
    },
    "timing": {
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-01T00:01:30Z",
        "duration_seconds": 90
    }
}
```

## Rate Limiting

APIs respect rate limits for external services:

| Service | Rate Limit | Handling |
|---------|------------|----------|
| Notion API | 3 requests/second | Automatic backoff |
| OpenAI API | Varies by model | Queue management |
| Anthropic API | Varies by plan | Exponential backoff |
| Slack API | Varies by method | Built-in throttling |

## SDK and Client Libraries

### Python SDK (Built-in)
```python
from nomad import NomadClient

client = NomadClient(config_file="config.env")
result = client.process_tasks(mode="refine")
```

### REST API (Future)
```bash
curl -X POST http://localhost:8080/api/v1/tasks/process \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "refine"}'
```

## Versioning

Nomad uses semantic versioning for API compatibility:

- **Major Version**: Breaking changes to APIs
- **Minor Version**: New features, backward compatible
- **Patch Version**: Bug fixes, backward compatible

### API Compatibility Matrix

| Nomad Version | API Version | Python Support | Changes |
|---------------|-------------|----------------|---------|
| 0.1.x | v1 | 3.8+ | Initial release |
| 0.2.x | v1 | 3.8+ | Enhanced features, no breaking changes |
| 0.3.x (planned) | v2 | 3.9+ | New APIs, some breaking changes |

## Getting Help

- **API Reference**: Detailed documentation in this section
- **Examples**: [Code examples](../examples/) for common use cases
- **Issues**: [Report API issues](https://github.com/nomad-notion-automation/nomad/issues)
- **Discussions**: [API questions and discussions](https://github.com/nomad-notion-automation/nomad/discussions)

## Contributing

To contribute to the APIs:

1. Review [API Design Guidelines](../development/api-design-guidelines.md)
2. Check [Contributing Guide](../contributing/)
3. Submit pull requests with tests and documentation
4. Follow [Code Style Guidelines](../development/code-style.md)

---

*API documentation for Nomad v0.2.0. For other versions, see the [changelog](../changelog/).*
