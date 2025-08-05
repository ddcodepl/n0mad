# Nomad Installation Guide

Welcome to the Nomad installation guide. This section provides comprehensive instructions for installing Nomad on your system using various methods.

## Quick Installation (Recommended)

For most users, the automatic installation script is the fastest way to get started:

```bash
curl -sSL https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh | bash
```

## Installation Methods

Choose the installation method that best fits your needs:

### 🚀 [Quick Install](quick-install.md)
**Recommended for most users**
- Automatic installation script
- Sets up everything you need
- Works on macOS, Linux, and WSL

### 📦 [Manual Installation](manual-installation.md)
**For custom setups**
- Step-by-step pip installation
- Full control over the process
- Customizable installation location

### 🐳 [Docker Installation](docker-installation.md)
**For containerized environments**
- Pre-built Docker images
- Isolated environment
- Easy deployment and scaling

### 👨‍💻 [Development Setup](development-setup.md)
**For contributors and developers**
- Source code installation
- Development dependencies
- Testing and debugging setup

## Platform-Specific Guides

### Operating Systems
- **[Windows](platform-specific/windows.md)** - Windows 10/11 installation
- **[macOS](platform-specific/macos.md)** - macOS installation and setup  
- **[Linux](platform-specific/linux.md)** - Linux distribution guides
- **[Cloud Platforms](platform-specific/cloud-platforms.md)** - AWS, Azure, GCP deployment

## System Requirements

Before installing Nomad, ensure your system meets these requirements:

### Minimum Requirements
- **Python**: 3.8 or higher
- **Memory**: 512 MB RAM
- **Storage**: 100 MB free disk space
- **Network**: Internet connectivity for API calls

### Recommended Requirements
- **Python**: 3.9 or higher
- **Memory**: 1 GB RAM or more
- **Storage**: 500 MB free disk space
- **Network**: Stable internet connection

### Dependencies
Nomad automatically installs these Python packages:
- `aiohttp` (>=3.9.0) - Async HTTP client
- `notion-client` (>=2.2.1) - Notion API client
- `openai` (>=1.35.0) - OpenAI API client
- `psutil` (>=7.0.0) - System monitoring
- `python-dotenv` (>=1.0.1) - Environment variable management

## Pre-Installation Checklist

Before installing Nomad, complete these steps:

- [ ] **Check Python Version**: Ensure Python 3.8+ is installed
- [ ] **Verify pip**: Confirm pip package manager is available
- [ ] **Internet Connection**: Ensure stable internet connectivity
- [ ] **Permissions**: Verify you have appropriate installation permissions
- [ ] **API Keys**: Gather required API keys (see [Configuration](#configuration))

### Check Python Version
```bash
python --version
# or
python3 --version
```

Expected output: `Python 3.8.x` or higher

### Check pip
```bash
pip --version
# or  
python -m pip --version
```

## Quick Start After Installation

Once Nomad is installed, follow these steps to get started:

### 1. Verify Installation
```bash
nomad --version
```

### 2. Create Configuration
```bash
nomad --config-create
```

### 3. Set Up API Keys
Edit your configuration file with required API keys:
- Notion API token
- Notion database ID
- At least one AI provider API key (OpenAI, Anthropic, or OpenRouter)

### 4. Check Configuration
```bash
nomad --config-status
```

### 5. Run Health Check
```bash
nomad --health-check
```

### 6. Start Processing
```bash
nomad --help  # See all available commands
nomad --refine  # Process "To Refine" status tasks
```

## Configuration Overview

Nomad requires several API keys and configuration settings. Here's a quick overview:

### Required Configuration
```env
# Notion Integration (Required)
NOTION_TOKEN=secret_your_notion_integration_token
NOTION_BOARD_DB=your_notion_database_id

# AI Provider (At least one required)
OPENAI_API_KEY=sk-your_openai_api_key
ANTHROPIC_API_KEY=sk-ant-your_anthropic_api_key
OPENROUTER_API_KEY=sk-or-your_openrouter_api_key
```

### Optional Configuration
```env
# Application Settings
NOMAD_HOME=~/.nomad
NOMAD_TASKS_DIR=~/.nomad/tasks
NOMAD_LOG_LEVEL=INFO
NOMAD_MAX_CONCURRENT_TASKS=3

# Slack Integration (Optional)
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL_GENERAL=C1234567890
```

For detailed configuration instructions, see the [Configuration Guide](../configuration/).

## API Keys Setup

Nomad integrates with several services. Here's how to get the required API keys:

### Notion API Key 🔑
1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the "Internal Integration Token"
4. Share your database with the integration
5. Copy the database ID from your database URL

### AI Provider Keys 🤖

#### OpenAI
1. Visit [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-`)

#### Anthropic (Claude)
1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Go to API Keys section  
3. Create a new key (starts with `sk-ant-`)

#### OpenRouter
1. Visit [OpenRouter Keys](https://openrouter.ai/keys)
2. Create a new API key
3. Copy the key (starts with `sk-or-`)

## Troubleshooting Installation Issues

### Common Problems and Solutions

#### Command Not Found
**Problem**: `nomad: command not found` after installation

**Solutions**:
```bash
# Add to PATH (Linux/macOS)
export PATH=$PATH:~/.local/bin

# Use full path
~/.local/bin/nomad --version

# Reinstall with --user flag
pip install --user nomad-notion-automation
```

#### Permission Errors
**Problem**: Permission denied during installation

**Solutions**:
```bash
# Use user installation
pip install --user nomad-notion-automation

# Use virtual environment
python -m venv nomad-env
source nomad-env/bin/activate  # Windows: nomad-env\Scripts\activate
pip install nomad-notion-automation
```

#### Python Version Issues
**Problem**: Unsupported Python version

**Solutions**:
1. Install Python 3.8+ from [python.org](https://python.org)
2. Use pyenv to manage Python versions
3. Use specific Python version: `python3.9 -m pip install nomad-notion-automation`

For more troubleshooting help, see [Installation Troubleshooting](troubleshooting-installation.md).

## Next Steps

After successful installation:

1. **[Configuration Setup](../configuration/)** - Configure Nomad for your environment
2. **[Quick Start Guide](../usage/quick-start.md)** - Learn basic Nomad usage
3. **[Processing Modes](../usage/processing-modes/)** - Understand different processing modes
4. **[Integration Guides](../integrations/)** - Set up integrations with other services

## Getting Help

- **Documentation**: Browse the [full documentation](../README.md)
- **Issues**: [Report bugs or request features](https://github.com/nomad-notion-automation/nomad/issues)
- **Discussions**: [Community discussions](https://github.com/nomad-notion-automation/nomad/discussions)
- **Troubleshooting**: [Common problems and solutions](../troubleshooting/)

---

*Installation guide for Nomad v0.2.0. For other versions, see the [changelog](../changelog/).*