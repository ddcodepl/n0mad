# Nomad Application Architecture Design

## Overview
This document outlines the new modular directory structure and architecture for the Nomad application, designed to improve maintainability, testability, and separation of concerns.

## New Directory Structure

```
nomad/
├── entry/                    # Application entry points
│   ├── __init__.py
│   └── main.py              # Unified entry point (merges main.py + main_workflow.py)
├── clients/                 # External service integrations
│   ├── __init__.py
│   ├── notion_wrapper.py    # Notion API client
│   ├── openai_client.py     # OpenAI API client
│   ├── openrouter_client.py # OpenRouter API client
│   └── claude_engine_invoker.py # Claude engine integration
├── core/                    # Core business logic
│   ├── __init__.py
│   ├── processors/          # Task processing logic
│   │   ├── __init__.py
│   │   ├── content_processor.py
│   │   ├── multi_queue_processor.py
│   │   ├── simple_queued_processor.py
│   │   └── multi_status_processor.py
│   ├── managers/            # State and lifecycle management
│   │   ├── __init__.py
│   │   ├── status_transition_manager.py
│   │   ├── feedback_manager.py
│   │   └── task_file_manager.py
│   └── operations/          # Data operations
│       ├── __init__.py
│       ├── database_operations.py
│       └── command_executor.py
├── utils/                   # Utilities and helpers
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── logging_config.py   # Logging configuration
│   ├── file_operations.py  # File system operations
│   ├── task_status.py      # Task status definitions
│   ├── task_locking.py     # Task locking mechanisms
│   ├── security_validator.py # Security validation
│   ├── provider_router.py  # API provider routing
│   ├── model_parser.py     # Model parsing utilities
│   ├── performance_monitor.py # Performance monitoring
│   ├── performance_integration.py # Performance integration
│   ├── polling_scheduler.py # Polling management
│   └── polling_strategies.py # Polling strategies
├── logs/                    # Session log files
├── tests/                   # All test files (moved from root)
└── data/                    # Application data (formerly src/tasks)
    ├── pre-refined/
    ├── refined/
    ├── summary/
    └── tasks/
```

## Architecture Principles

### 1. Separation of Concerns
- **Clients**: Handle external API integrations
- **Core**: Contain business logic and domain operations
- **Utils**: Provide shared utilities and configurations
- **Entry**: Serve as application entry points

### 2. Unified Entry Point
- Single `entry/main.py` replaces both `src/main.py` and `main_workflow.py`
- Uses command-line arguments to determine operation mode
- Implements Facade pattern for clean interface

### 3. Modular Design
- Each module has a single responsibility
- Clear dependency hierarchy: entry → core → clients/utils
- Easy to test and maintain individual components

### 4. Standardized Logging
- All logs written to `./logs/` directory
- Timestamped session files
- Consistent logging format across all modules

## Module Categorization

### Clients (External Integrations)
- `notion_wrapper.py` - Notion API operations
- `openai_client.py` - OpenAI API operations  
- `openrouter_client.py` - OpenRouter API operations
- `claude_engine_invoker.py` - Claude engine integration

### Core Business Logic
- **Processors**: Task processing and workflow logic
- **Managers**: State management and lifecycle operations
- **Operations**: Data operations and command execution

### Utilities
- Configuration, logging, file operations
- Task definitions and locking
- Performance monitoring and security
- Provider routing and model parsing

## Import Path Migration

### Old → New Import Mappings
```python
# Clients
from notion_wrapper → from clients.notion_wrapper
from openai_client → from clients.openai_client
from openrouter_client → from clients.openrouter_client
from claude_engine_invoker → from clients.claude_engine_invoker

# Core - Processors
from content_processor → from core.processors.content_processor
from multi_queue_processor → from core.processors.multi_queue_processor
from simple_queued_processor → from core.processors.simple_queued_processor
from multi_status_processor → from core.processors.multi_status_processor

# Core - Managers
from status_transition_manager → from core.managers.status_transition_manager
from feedback_manager → from core.managers.feedback_manager
from task_file_manager → from core.managers.task_file_manager

# Core - Operations
from database_operations → from core.operations.database_operations
from command_executor → from core.operations.command_executor

# Utils
from config → from utils.config
from logging_config → from utils.logging_config
from file_operations → from utils.file_operations
from task_status → from utils.task_status
from task_locking → from utils.task_locking
from security_validator → from utils.security_validator
from provider_router → from utils.provider_router
from model_parser → from utils.model_parser
from performance_monitor → from utils.performance_monitor
from performance_integration → from utils.performance_integration
from polling_scheduler → from utils.polling_scheduler
from polling_strategies → from utils.polling_strategies
```

## Entry Point Design

### Unified Main Application
The new `entry/main.py` will:
1. Parse command-line arguments for mode selection
2. Initialize performance monitoring
3. Configure logging with session files
4. Route to appropriate processing mode
5. Handle graceful shutdown

### Command-Line Interface
```bash
python entry/main.py                    # Continuous polling mode
python entry/main.py --refine          # Refine mode
python entry/main.py --prepare         # Prepare mode  
python entry/main.py --queued          # Queued mode
python entry/main.py --multi           # Multi-status mode
```

## Dependency Injection Strategy

### Logger Injection
- Centralized logger configuration in `utils/logging_config.py`
- Session-based log files in `./logs/`
- Consistent format across all modules

### Configuration Management
- Environment-based configuration in `utils/config.py`
- Centralized API key management
- Module-specific settings

### Client Interface Standardization
```python
# Common interface for all clients
class BaseClient:
    def execute(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Standard execution interface"""
        pass
    
    def test_connection(self) -> bool:
        """Connection validation"""
        pass
```

## Migration Strategy

1. **Create New Directory Structure** (Task 173)
2. **Relocate Modules by Category** (Tasks 174-176)
3. **Create Unified Entry Point** (Task 177)
4. **Implement Standardized Logging** (Task 178)
5. **Update All Import Statements** (Task 179)
6. **Execute Comprehensive Testing** (Task 180)

## Benefits

1. **Improved Maintainability**: Clear module boundaries
2. **Enhanced Testability**: Isolated components
3. **Better Performance**: Centralized monitoring
4. **Simplified Deployment**: Single entry point
5. **Consistent Logging**: Unified log management
6. **Scalable Architecture**: Easy to add new modules

## Validation Criteria

- [ ] All existing functionality preserved
- [ ] Import statements updated correctly
- [ ] Tests pass with new structure
- [ ] Performance targets maintained
- [ ] Logging consistently configured
- [ ] Entry point handles all modes