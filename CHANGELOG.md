# Changelog

All notable changes to the Nomad project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-05

### Added
- **Global Installation Support**: Complete redesign for pip-installable package
- **Enhanced Security Framework**: Comprehensive API key validation and masking
- **Multi-Provider AI Integration**: Support for OpenAI, Anthropic, and OpenRouter APIs
- **Global Configuration System**: Centralized environment variable management
- **Comprehensive CLI Interface**: Rich command-line tools with help and validation
- **Directory-Independent Execution**: Run from any directory with automatic path resolution
- **Installation Scripts**: Automated installation with `install.sh`
- **Configuration Management Commands**:
  - `--config-help`: Show configuration assistance
  - `--config-create`: Generate configuration templates
  - `--config-status`: Display current configuration state
- **Enhanced Error Handling**: Better error messages with configuration guidance
- **Security Features**:
  - API key format validation
  - Credential masking in logs and errors
  - Secure configuration file handling
  - Environment leak detection
- **Package Metadata**: Complete PyPI-ready package configuration
- **Comprehensive Documentation**: Updated README with installation and usage guides

### Changed
- **Package Structure**: Reorganized for global installation compatibility
- **Entry Point**: Updated to `nomad` command for global access
- **Configuration Loading**: Multi-source configuration with precedence handling
- **API Client Initialization**: Enhanced with security validation and error handling
- **Logging System**: Improved with session management and secure credential handling
- **Error Messages**: More user-friendly with actionable guidance

### Improved
- **Performance**: Optimized configuration loading and validation
- **Reliability**: Enhanced error recovery and retry mechanisms
- **User Experience**: Streamlined installation and configuration process
- **Security**: Comprehensive credential protection throughout the application

### Technical Changes
- **Python Version Support**: Extended to Python 3.8+
- **Dependencies**: Updated to latest stable versions
- **Build System**: Modern setuptools configuration with pyproject.toml
- **Development Tools**: Added linting, formatting, and type checking support

## [0.1.0] - 2024-12-01

### Added
- Initial release of Notion Developer automation tool
- Basic Notion API integration for task polling
- OpenAI GPT-4 integration for content processing
- Automatic markdown file generation
- Continuous polling with 60-second intervals
- Basic logging and error handling
- Performance metrics tracking
- Graceful shutdown support

### Core Features
- **Task Processing**: Automated refinement of Notion tasks with "To Refine" status
- **Content Generation**: AI-powered task refinement using OpenAI GPT
- **File Management**: Automatic saving of processed content to markdown files
- **Database Operations**: CRUD operations on Notion databases
- **Monitoring**: Basic performance and processing metrics

### Initial Architecture
- Modular client architecture for Notion and OpenAI
- Basic configuration through environment variables
- Simple file-based task management
- Local development setup with uv/pip

---

## Upgrade Guide

### From v0.1.0 to v0.2.0

1. **Installation**: Uninstall old version and use new global installation:
   ```bash
   pip uninstall notion-developer  # if previously installed
   pip install nomad-notion-automation
   ```

2. **Configuration**: Update environment variables:
   - No changes to existing variables required
   - New optional variables available for enhanced features
   - Use `nomad --config-help` for guidance

3. **Usage**: Update command usage:
   - Old: `python main.py --refine`
   - New: `nomad --refine`

4. **Global Access**: The tool is now available system-wide:
   ```bash
   nomad --version  # works from any directory
   ```

## Breaking Changes

### v0.2.0
- **Command Name**: Changed from local script execution to global `nomad` command
- **Package Name**: Renamed from `notion-developer` to `nomad-notion-automation`
- **Configuration**: Enhanced validation may require API key format updates
- **Entry Point**: Main script moved from `main.py` to `entry/main.py`

## Migration Notes

### Configuration Files
- Existing `.env` files continue to work
- New global configuration system available
- Enhanced security features may show warnings for existing configurations

### API Keys
- Existing API keys continue to work
- Enhanced validation provides better error messages
- Security features mask keys in logs and errors

### File Paths
- Task files now use global directory structure by default
- Existing local files are preserved
- Use `--working-dir` to specify custom locations

---

*For more information about any release, check the [GitHub releases page](https://github.com/nomad-notion-automation/nomad/releases).*