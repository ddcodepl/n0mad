# AI Provider APIs

Nomad integrates with multiple AI providers to deliver intelligent task processing and content generation capabilities. This document covers all supported AI provider APIs and their integration patterns.

## Overview

Nomad supports three primary AI providers:

1. **OpenAI** - GPT models for general-purpose AI processing
2. **Anthropic** - Claude models for advanced reasoning and analysis
3. **OpenRouter** - Multi-model access with provider routing and fallback

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Task Input    │    │  Provider Router │    │  AI Providers   │
│                 │───▶│                  │───▶│                 │
│ - Content       │    │ - Model Selection│    │ - OpenAI        │
│ - Requirements  │    │ - Load Balancing │    │ - Anthropic     │
│ - Context       │    │ - Fallback Logic │    │ - OpenRouter    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                  │
                                  ▼
                       ┌──────────────────┐
                       │  Processed       │
                       │  Content         │
                       │                  │
                       │ - Enhanced Text  │
                       │ - Metadata       │
                       │ - Suggestions    │
                       └──────────────────┘
```

## Authentication

Each provider requires API keys configured as environment variables:

```env
# OpenAI (starts with sk-)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Anthropic (starts with sk-ant-)
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here

# OpenRouter (starts with sk-or-)
OPENROUTER_API_KEY=sk-or-your-openrouter-api-key-here
```

At least one provider must be configured for AI functionality to work.

## OpenAI Integration

### OpenAIClient Class

Primary interface for OpenAI API integration.

```python
from nomad.clients.openai_client import OpenAIClient

# Initialize client
client = OpenAIClient()

# Process content
result = client.process_content(
    content="Task content to process",
    task_type="refinement",
    context={"priority": "high"}
)
```

#### Constructor

```python
def __init__(
    self,
    api_key: Optional[str] = None,
    model: str = "gpt-4",
    max_tokens: int = 2000,
    temperature: float = 0.7
) -> None
```

**Parameters:**
- `api_key`: OpenAI API key (uses `OPENAI_API_KEY` if None)
- `model`: Model to use (e.g., "gpt-4", "gpt-3.5-turbo")
- `max_tokens`: Maximum tokens in response
- `temperature`: Creativity level (0.0-1.0)

#### Core Methods

##### process_content()

Main method for content processing with GPT models.

```python
def process_content(
    self,
    content: str,
    task_type: str = "general",
    context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters:**
- `content`: Text content to process
- `task_type`: Type of processing ("refinement", "analysis", "generation")
- `context`: Additional context for processing
- `model`: Override default model for this request

**Returns:**
```python
{
    "status": "success",
    "processed_content": "Enhanced content text",
    "original_content": "Original input content",
    "model_used": "gpt-4",
    "tokens_used": 1250,
    "processing_time": 2.3,
    "metadata": {
        "changes_made": ["grammar", "clarity", "structure"],
        "confidence_score": 0.95,
        "suggestions": ["Add more examples", "Consider user perspective"]
    }
}
```

**Example:**
```python
result = client.process_content(
    content="This task need better explanation of the process.",
    task_type="refinement",
    context={
        "target_audience": "developers",
        "tone": "technical",
        "priority": "high"
    }
)

print(f"Enhanced content: {result['processed_content']}")
print(f"Changes made: {result['metadata']['changes_made']}")
```

##### generate_content()

Generate new content based on prompts and requirements.

```python
def generate_content(
    self,
    prompt: str,
    content_type: str = "general",
    requirements: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Parameters:**
- `prompt`: Generation prompt
- `content_type`: Type of content to generate
- `requirements`: Specific requirements or constraints

**Example:**
```python
result = client.generate_content(
    prompt="Create a user guide for task automation",
    content_type="documentation",
    requirements={
        "length": "medium",
        "format": "markdown",
        "include_examples": True
    }
)
```

##### analyze_content()

Analyze content for insights, sentiment, or structure.

```python
def analyze_content(
    self,
    content: str,
    analysis_type: str = "general",
    focus_areas: Optional[List[str]] = None
) -> Dict[str, Any]
```

**Example:**
```python
analysis = client.analyze_content(
    content="Long technical document...",
    analysis_type="technical_review",
    focus_areas=["clarity", "completeness", "accuracy"]
)

print(f"Analysis score: {analysis['metadata']['overall_score']}")
print(f"Recommendations: {analysis['metadata']['recommendations']}")
```

### Supported Models

| Model | Use Case | Max Tokens | Cost Level |
|-------|----------|------------|------------|
| `gpt-4` | Complex reasoning, analysis | 8,192 | High |
| `gpt-4-32k` | Long document processing | 32,768 | Very High |
| `gpt-3.5-turbo` | General processing | 4,096 | Medium |
| `gpt-3.5-turbo-16k` | Extended context | 16,384 | Medium-High |

### Configuration Options

```python
# Custom configuration
client = OpenAIClient(
    model="gpt-4",
    max_tokens=3000,
    temperature=0.3,  # More focused responses
)

# Model-specific settings
client.set_model_config("gpt-4", {
    "max_tokens": 4000,
    "temperature": 0.5,
    "top_p": 0.9,
    "frequency_penalty": 0.1
})
```

## Anthropic (Claude) Integration

### ClaudeEngineInvoker Class

Interface for Anthropic Claude API integration.

```python
from nomad.clients.claude_engine_invoker import ClaudeEngineInvoker

# Initialize invoker
invoker = ClaudeEngineInvoker()

# Process with Claude
result = invoker.invoke_claude_engine(
    content="Content to process",
    model="claude-3-sonnet",
    task_type="analysis"
)
```

#### Constructor

```python
def __init__(
    self,
    api_key: Optional[str] = None,
    default_model: str = "claude-3-sonnet",
    timeout: int = 120
) -> None
```

#### Core Methods

##### invoke_claude_engine()

Main method for Claude processing.

```python
def invoke_claude_engine(
    self,
    content: str,
    model: str = "claude-3-sonnet",
    task_type: str = "general",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Parameters:**
- `content`: Content to process
- `model`: Claude model to use
- `task_type`: Processing task type
- `context`: Additional context

**Returns:**
```python
{
    "status": "success",
    "result": "Processed content",
    "model": "claude-3-sonnet",
    "usage": {
        "input_tokens": 1200,
        "output_tokens": 800,
        "total_tokens": 2000
    },
    "processing_time": 3.7,
    "metadata": {
        "reasoning_steps": ["analysis", "enhancement", "validation"],
        "confidence": 0.92
    }
}
```

### Supported Claude Models

| Model | Description | Context Window | Best For |
|-------|-------------|----------------|----------|
| `claude-3-opus` | Most capable model | 200K tokens | Complex analysis, creative tasks |
| `claude-3-sonnet` | Balanced performance | 200K tokens | General processing, reasoning |
| `claude-3-haiku` | Fast and efficient | 200K tokens | Quick processing, simple tasks |

### Advanced Features

#### Process Management

```python
# Long-running processes with monitoring
invoker = ClaudeEngineInvoker()

# Process with timeout and monitoring
result = invoker.invoke_with_monitoring(
    content=large_content,
    timeout=300,
    progress_callback=lambda p: print(f"Progress: {p}%")
)

# Cleanup processes if needed
invoker.cleanup_active_processes()
```

## OpenRouter Integration

### OpenRouterClient Class

Access to multiple AI models through OpenRouter's unified API.

```python
from nomad.clients.openrouter_client import OpenRouterClient

# Initialize client
client = OpenRouterClient()

# List available models
models = client.get_available_models()

# Process with specific model
result = client.process_content(
    content="Content to process",
    model="anthropic/claude-3-sonnet",
    provider_preferences=["anthropic", "openai"]
)
```

#### Constructor

```python
def __init__(
    self,
    api_key: Optional[str] = None,
    site_url: str = "nomad-automation",
    app_name: str = "Nomad Task Processor"
) -> None
```

#### Core Methods

##### get_available_models()

Retrieve list of available models and their capabilities.

```python
def get_available_models(self) -> List[Dict[str, Any]]
```

**Returns:**
```python
[
    {
        "id": "anthropic/claude-3-sonnet",
        "name": "Claude 3 Sonnet",
        "description": "Anthropic's balanced model",
        "pricing": {"prompt": 0.003, "completion": 0.015},
        "context_length": 200000,
        "capabilities": ["text", "analysis", "reasoning"]
    },
    {
        "id": "openai/gpt-4",
        "name": "GPT-4",
        "description": "OpenAI's most capable model",
        "pricing": {"prompt": 0.03, "completion": 0.06},
        "context_length": 8192,
        "capabilities": ["text", "code", "analysis"]
    }
]
```

##### process_content()

Process content with model selection and fallback.

```python
def process_content(
    self,
    content: str,
    model: Optional[str] = None,
    provider_preferences: Optional[List[str]] = None,
    fallback_models: Optional[List[str]] = None
) -> Dict[str, Any]
```

**Parameters:**
- `content`: Content to process
- `model`: Specific model ID to use
- `provider_preferences`: Preferred providers in order
- `fallback_models`: Models to try if primary fails

**Example:**
```python
result = client.process_content(
    content="Complex technical analysis needed",
    provider_preferences=["anthropic", "openai"],
    fallback_models=[
        "anthropic/claude-3-sonnet",
        "openai/gpt-4",
        "openai/gpt-3.5-turbo"
    ]
)
```

### Model Selection Strategy

OpenRouter automatically selects the best model based on:

1. **Provider Preferences**: Your preferred providers
2. **Task Requirements**: Content type and complexity
3. **Cost Optimization**: Balance between quality and cost
4. **Availability**: Real-time model availability
5. **Performance**: Historical performance for similar tasks

## Provider Router

### Automatic Provider Selection

Nomad includes intelligent provider routing:

```python
from nomad.utils.provider_router import ProviderRouter

router = ProviderRouter()

# Automatic provider selection based on task
result = router.process_task(
    content="Content to process",
    task_type="analysis",
    quality_preference="high",  # "high", "balanced", "fast"
    cost_preference="balanced"   # "low", "balanced", "high"
)
```

### Configuration

```python
# Configure provider preferences
router.set_preferences({
    "primary_provider": "anthropic",
    "fallback_providers": ["openai", "openrouter"],
    "max_cost_per_request": 0.50,
    "timeout_seconds": 120,
    "retry_attempts": 3
})

# Task-specific routing
router.configure_task_routing({
    "analysis": {"preferred": "anthropic", "model": "claude-3-sonnet"},
    "generation": {"preferred": "openai", "model": "gpt-4"},
    "refinement": {"preferred": "openai", "model": "gpt-3.5-turbo"}
})
```

## Error Handling

### Common Error Patterns

```python
from nomad.core.exceptions import AIProviderError, RateLimitError, ModelNotAvailableError

try:
    result = client.process_content(content)
except RateLimitError as e:
    print(f"Rate limit exceeded. Retry after: {e.retry_after} seconds")
    # Implement exponential backoff
except ModelNotAvailableError as e:
    print(f"Model {e.model} not available. Trying fallback...")
    # Try alternative model
except AIProviderError as e:
    print(f"Provider error: {e.message}")
    # Log error and try different provider
```

### Retry Logic

```python
import time
from typing import Callable

def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0
):
    """Retry function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(base_delay)

# Usage
result = retry_with_backoff(
    lambda: client.process_content(content),
    max_retries=3
)
```

## Performance Optimization

### Batch Processing

```python
# Process multiple items efficiently
contents = ["content1", "content2", "content3"]

# Sequential processing with shared context
results = []
for content in contents:
    result = client.process_content(
        content=content,
        context={"batch_mode": True}
    )
    results.append(result)

# Concurrent processing (use with rate limit consideration)
import asyncio

async def process_batch(contents):
    tasks = [
        client.process_content_async(content)
        for content in contents
    ]
    return await asyncio.gather(*tasks)
```

### Caching

```python
from functools import lru_cache
import hashlib

class CachedAIClient:
    def __init__(self, client):
        self.client = client

    @lru_cache(maxsize=128)
    def process_content_cached(self, content_hash, content, task_type):
        return self.client.process_content(content, task_type)

    def process_content(self, content, task_type="general"):
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return self.process_content_cached(content_hash, content, task_type)

# Usage
cached_client = CachedAIClient(OpenAIClient())
result = cached_client.process_content("Same content")  # Cached on repeat
```

## Usage Examples

### Task Refinement Workflow

```python
from nomad.clients import OpenAIClient, ClaudeEngineInvoker

def refine_task_content(task_content, task_context):
    """Complete task refinement workflow using multiple AI providers."""

    # Step 1: Initial analysis with Claude
    claude = ClaudeEngineInvoker()
    analysis = claude.invoke_claude_engine(
        content=task_content,
        task_type="analysis",
        context=task_context
    )

    # Step 2: Content enhancement with GPT-4
    openai = OpenAIClient(model="gpt-4")
    enhanced = openai.process_content(
        content=task_content,
        task_type="refinement",
        context={
            "analysis_insights": analysis["metadata"],
            **task_context
        }
    )

    # Step 3: Quality validation
    validation = claude.invoke_claude_engine(
        content=enhanced["processed_content"],
        task_type="validation",
        context={"original_content": task_content}
    )

    return {
        "original": task_content,
        "enhanced": enhanced["processed_content"],
        "analysis": analysis,
        "validation": validation,
        "total_tokens": (
            analysis["usage"]["total_tokens"] +
            enhanced["tokens_used"] +
            validation["usage"]["total_tokens"]
        )
    }

# Usage
result = refine_task_content(
    task_content="Create user authentication system",
    task_context={
        "project_type": "web_application",
        "tech_stack": ["python", "flask", "postgresql"],
        "security_requirements": "high"
    }
)
```

### Multi-Provider Content Generation

```python
def generate_comprehensive_content(topic, requirements):
    """Generate content using multiple providers for different aspects."""

    providers = {
        "outline": OpenAIClient(model="gpt-4"),
        "content": ClaudeEngineInvoker(),
        "review": OpenRouterClient()
    }

    # Generate outline
    outline = providers["outline"].generate_content(
        prompt=f"Create detailed outline for: {topic}",
        content_type="outline",
        requirements=requirements
    )

    # Generate full content
    content = providers["content"].invoke_claude_engine(
        content=outline["result"],
        task_type="content_generation",
        context={"topic": topic, "requirements": requirements}
    )

    # Peer review
    review = providers["review"].process_content(
        content=content["result"],
        model="anthropic/claude-3-sonnet",
        provider_preferences=["anthropic"]
    )

    return {
        "outline": outline,
        "content": content,
        "review": review,
        "final_content": review["processed_content"]
    }
```

## Best Practices

### 1. Provider Selection
- Use Claude for complex reasoning and analysis
- Use GPT-4 for creative and general-purpose tasks
- Use GPT-3.5-turbo for fast, cost-effective processing
- Use OpenRouter for model diversity and fallback

### 2. Error Handling
- Always implement retry logic with exponential backoff
- Use fallback providers for reliability
- Monitor rate limits and adjust accordingly
- Log errors for debugging and analysis

### 3. Cost Optimization
- Cache frequent requests when appropriate
- Use less expensive models for simple tasks
- Implement request batching where possible
- Monitor usage and costs regularly

### 4. Security
- Never log API keys or responses containing sensitive data
- Use environment variables for API key management
- Implement proper error handling to avoid exposing keys
- Regularly rotate API keys

### 5. Performance
- Use async processing for concurrent requests
- Implement connection pooling for high-volume usage
- Monitor response times and adjust timeouts
- Use streaming for long responses when available

---

*AI Provider API documentation for Nomad v0.2.0. For more examples and advanced usage, see the [examples directory](../examples/ai-integration/).*
