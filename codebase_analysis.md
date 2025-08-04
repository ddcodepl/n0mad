# Codebase Reconnaissance and Analysis Report

## 1. Project Overview
- **Project Name**: nomad
- **Description**: Notion task refinement automation tool
- **Main Technology**: Python 3.11+
- **Architecture Pattern**: Modular service-oriented design with multiple entry points

## 2. Top-Level Scripts and Entry Points

### Primary Entry Points
- **src/main.py**: Unified main application with multiple operational modes:
  - `--refine`: Process tasks with 'To Refine' status
  - `--prepare`: Process tasks with 'Prepare Tasks' status
  - `--queued`: Process tasks with 'Queued to run' status
  - `--multi`: Process multiple status types
  - No args: Continuous polling mode

### Secondary Entry Points
- **run.py**: Alternative runner
- **execute_claude_interactive.py**: Claude engine interactive execution
- **force_claude_implementation.py**: Forced Claude implementation
- **run_claude_unrestricted.py**: Unrestricted Claude runner
- **debug_schema.py**: Schema debugging utility

## 3. Core Module Inventory

### Client-Related Modules
- **notion_wrapper.py**: Notion API client wrapper
- **openai_client.py**: OpenAI API client 
- **openrouter_client.py**: OpenRouter API client
- **claude_engine_invoker.py**: Claude engine invocation system

### Core Business Logic Modules
- **content_processor.py**: Content processing engine
- **database_operations.py**: Database operations abstraction
- **status_transition_manager.py**: Task status transitions
- **task_status.py**: Task status definitions
- **multi_status_processor.py**: Multi-status processing logic
- **simple_queued_processor.py**: Simple queued task processor
- **multi_queue_processor.py**: Multi-queue processing system

### Utility and Helper Modules
- **config.py**: Configuration management
- **logging_config.py**: Logging configuration
- **file_operations.py**: File system operations
- **task_file_manager.py**: Task file management
- **command_executor.py**: System command execution
- **model_parser.py**: AI model parsing utilities
- **provider_router.py**: Provider routing logic
- **security_validator.py**: Security validation
- **performance_monitor.py**: Performance monitoring
- **performance_integration.py**: Performance system integration
- **feedback_manager.py**: User feedback management
- **polling_scheduler.py**: Polling scheduling system
- **polling_strategies.py**: Polling strategy implementations
- **task_locking.py**: Task locking mechanisms

## 4. Directory Structure Analysis

### Current Structure
```
nomad/
├── src/                           # Main source code
│   ├── tasks/                     # Task-related files
│   │   ├── pre-refined/           # Pre-refinement task files
│   │   ├── refined/               # Refined task files
│   │   ├── summary/               # Task summaries
│   │   └── tasks/                 # Task JSON files
│   └── *.py                       # Core modules (30+ files)
├── test_*.py                      # Test files (20+ files)
├── *.py                          # Top-level scripts (8+ files)
├── *.md                          # Documentation files
├── node_modules/                  # Node.js dependencies
└── Configuration files
```

## 5. Integration Points and Dependencies

### External Dependencies
- **notion-client**: Notion API integration
- **openai**: OpenAI API integration
- **aiohttp**: Async HTTP client
- **python-dotenv**: Environment variable management
- **psutil**: System process utilities

### Internal Dependencies (Import Graph)
- **main.py** → 15+ internal modules (central orchestrator)
- **Multi-layered architecture**: Client → Core Logic → Utilities
- **Heavy cross-dependencies** between core modules
- **Performance monitoring** integrated across all components

## 6. Configuration and Environment

### Configuration Files
- **pyproject.toml**: Project configuration and dependencies
- **requirements.txt**: Python dependencies
- **package.json**: Node.js dependencies (process-tasks.js)
- **.env**: Environment variables (API keys, configuration)

### Logging Configuration
- **File logging**: nomad.log in project root
- **Console logging**: stdout stream
- **Structured logging**: timestamps, log levels, module names
- **Session logging**: Performance and processing metrics

## 7. Test Suite Analysis

### Test Coverage Areas
- **Configuration**: API keys, polling, integration
- **Database Operations**: Notion database interactions
- **File Operations**: Task file management
- **Performance**: Monitoring and metrics
- **Security**: Validation and compliance
- **Provider Integration**: OpenAI, OpenRouter clients
- **Processing Logic**: Status transitions, queuing

### Test File Count: 20+ test files covering major components

## 8. Build and Deployment

### Python Environment
- **UV package manager**: Used for dependency management
- **Python 3.11+**: Minimum version requirement
- **Script entry point**: `nomad = "src.main:main"`

### Node.js Components
- **process-tasks.js**: Task processing script
- **package-lock.json**: Locked Node.js dependencies

## 9. Task Master Integration

### Task Master Structure
- **.taskmaster/**: Task Master AI integration directory
- **CLAUDE.md**: Claude Code instructions and workflows
- **Tasks management**: Integrated with Task Master AI system
- **Git integration**: Task tracking and version control

## 10. Current Architecture Issues (Reorganization Targets)

### Problems Identified
1. **Flat src/ structure**: All modules in single directory (30+ files)
2. **Mixed concerns**: Client, core logic, and utilities intermingled
3. **Complex import chains**: Deep dependency graphs
4. **Multiple entry points**: Scattered across root and src/
5. **Inconsistent logging**: Mixed patterns across modules
6. **Test file placement**: Tests scattered in root directory

### Dependencies for Reorganization
- **Import statement updates**: 100+ import statements to modify
- **Path references**: Configuration and file operations
- **Test imports**: All test files need import updates
- **Entry point scripts**: Multiple scripts reference src/ modules
- **Performance monitoring**: Integrated across all components
- **CLI argument parsing**: Multiple modes and configurations

## 11. Integration Points for Reorganization

### Critical Integration Points
1. **main.py**: Central orchestrator importing 15+ modules
2. **Performance monitoring**: Cross-cutting concern
3. **Logging system**: Used across all modules
4. **Configuration management**: Centralized config access
5. **File operations**: Path-dependent operations
6. **Task Master**: .taskmaster/ directory structure
7. **Test suite**: Import dependencies on src/ structure

### External Service Integrations
- **Notion API**: Database operations and content management
- **OpenAI/OpenRouter**: AI processing services
- **Claude Engine**: Code execution and processing
- **File System**: Task file management and processing

## 12. Recommendations for Reorganization

### Proposed New Structure
```
nomad/
├── entry/                     # Entry points and CLI
├── clients/                   # External service clients
├── core/                     # Core business logic
├── utils/                    # Utility and helper modules
├── tests/                    # All test files
└── logs/                     # Session logs directory
```

### Migration Strategy
1. **Start with task 171**: Complete this reconnaissance
2. **Design architecture (172)**: Define new structure
3. **Create directories (173)**: Establish foundation
4. **Move modules systematically (174-176)**: By category
5. **Merge entry points (177)**: Unified entry point
6. **Update imports (179)**: Systematic import updates
7. **Implement logging (178)**: Standardized session logging
8. **Comprehensive testing (180)**: Validate all functionality

This analysis provides the foundation for the remaining reorganization tasks.