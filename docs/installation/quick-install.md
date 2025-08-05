# Quick Installation Guide

Get Nomad up and running in just a few minutes with our automatic installation script.

## Overview

The quick installation method uses an automated script that handles all the setup for you, including:
- Python dependency verification
- Package installation
- Basic configuration setup
- Path configuration
- Initial verification

**Perfect for**: First-time users, quick evaluation, standard setups

## Prerequisites

### System Requirements
- **Operating System**: macOS, Linux, or Windows with WSL
- **Python**: 3.8 or higher
- **Internet**: Stable internet connection
- **Permissions**: Ability to install packages (may need sudo)

### Quick Prerequisites Check
```bash
# Check Python version (should be 3.8+)
python3 --version

# Check pip is available
python3 -m pip --version

# Check internet connectivity
curl -s https://pypi.org > /dev/null && echo "✅ Internet OK" || echo "❌ Internet issue"
```

## Installation

### One-Line Installation
```bash
curl -sSL https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh | bash
```

### What the Script Does
The installation script will:

1. **Check Prerequisites**: Verify Python version and dependencies
2. **Install Package**: Download and install Nomad via pip
3. **Setup Paths**: Configure command-line access
4. **Create Config**: Generate configuration template
5. **Verify Installation**: Test that everything works

### Expected Output
```
🚀 Starting Nomad Installation...

✅ Python 3.9.7 detected (requirement: 3.8+)
✅ pip 21.2.4 available
✅ Internet connectivity confirmed

📦 Installing nomad-notion-automation...
Successfully installed nomad-notion-automation-0.2.0

🔧 Setting up configuration...
Configuration template created at: ~/.nomad/config.env

✅ Installation completed successfully!

🎉 Nomad v0.2.0 is ready to use!
```

### Alternative: Manual Script Download
If you prefer to review the script before running:

```bash
# Download the script
curl -sSL https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh -o install-nomad.sh

# Review the script
cat install-nomad.sh

# Run the script
bash install-nomad.sh
```

## Post-Installation Setup

### 1. Verify Installation
```bash
nomad --version
```

Expected output:
```
Nomad v0.2.0 - Notion Automation Tool
```

### 2. Check Installation Status
```bash
nomad --config-status
```

This will show you what configuration is needed.

### 3. Set Up Required API Keys

The installation creates a configuration template at `~/.nomad/config.env`. Edit this file to add your API keys:

```bash
# Edit configuration file
nano ~/.nomad/config.env
# or use your preferred editor
code ~/.nomad/config.env
```

Add your API keys:
```env
# Notion Integration (Required)
NOTION_TOKEN=secret_your_notion_token_here
NOTION_BOARD_DB=your_database_id_here

# AI Provider (At least one required)
OPENAI_API_KEY=sk-your_openai_key_here
# ANTHROPIC_API_KEY=sk-ant-your_anthropic_key_here
# OPENROUTER_API_KEY=sk-or-your_openrouter_key_here
```

### 4. Activate Configuration
```bash
# Set the config file environment variable
export NOMAD_CONFIG_FILE=~/.nomad/config.env

# Add to your shell profile for persistence
echo 'export NOMAD_CONFIG_FILE=~/.nomad/config.env' >> ~/.bashrc
# or for zsh users:
echo 'export NOMAD_CONFIG_FILE=~/.nomad/config.env' >> ~/.zshrc
```

### 5. Final Verification
```bash
# Check configuration
nomad --config-status

# Run health check
nomad --health-check
```

## Getting API Keys

### Notion Setup (Required)

1. **Create Notion Integration**:
   - Go to [Notion Integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Name it "Nomad Automation"
   - Select your workspace
   - Click "Submit"

2. **Get the Token**:
   - Copy the "Internal Integration Token" (starts with `secret_`)
   - This is your `NOTION_TOKEN`

3. **Share Database**:
   - Go to your Notion database
   - Click "Share" in the top-right
   - Invite your integration by name
   - Set permissions to "Can edit"

4. **Get Database ID**:
   - Copy the database URL from your browser
   - Extract the database ID (32-character string after the last `/` and before any `?`)
   - This is your `NOTION_BOARD_DB`

### AI Provider Setup (Choose One)

#### Option 1: OpenAI (Recommended)
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Click "Create new secret key"
3. Copy the key (starts with `sk-`)
4. Add to config as `OPENAI_API_KEY`

#### Option 2: Anthropic (Claude)
1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Navigate to "API Keys"
3. Create a new key
4. Copy the key (starts with `sk-ant-`)
5. Add to config as `ANTHROPIC_API_KEY`

#### Option 3: OpenRouter (Multi-Model)
1. Go to [OpenRouter](https://openrouter.ai/keys)
2. Create an account and get credits
3. Generate an API key
4. Copy the key (starts with `sk-or-`)
5. Add to config as `OPENROUTER_API_KEY`

## First Run

Once configured, try your first Nomad command:

```bash
# See all available commands
nomad --help

# Check your configuration
nomad --config-status

# Process tasks in "To Refine" status
nomad --refine
```

## Quick Start Commands

```bash
# Basic operations
nomad --version              # Check version
nomad --help                 # Show help
nomad --config-status        # Check configuration
nomad --health-check         # System health check

# Processing modes
nomad --refine              # Process "To Refine" tasks
nomad --prepare             # Process "Prepare Tasks"
nomad --queued              # Process "Queued to run" tasks
nomad --multi               # Multi-status processing
nomad                       # Continuous polling (default)

# Configuration management
nomad --config-help         # Configuration help
nomad --config-create       # Create config template
```

## Troubleshooting Quick Installation

### Script Fails to Download
**Problem**: `curl` command fails or script download errors

**Solutions**:
```bash
# Try with wget instead
wget -qO- https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh | bash

# Or download manually
curl -L https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh -o install.sh
bash install.sh
```

### Permission Denied
**Problem**: Installation fails with permission errors

**Solutions**:
```bash
# Install to user directory
curl -sSL https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh | bash -s -- --user

# Or use sudo (not recommended)
curl -sSL https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh | sudo bash
```

### Command Not Found After Installation
**Problem**: `nomad` command not recognized

**Solutions**:
```bash
# Reload shell
source ~/.bashrc  # or ~/.zshrc

# Check if installed in user directory
ls ~/.local/bin/nomad

# Add to PATH manually
export PATH=$PATH:~/.local/bin
echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
```

### Python Version Issues
**Problem**: Script complains about Python version

**Solutions**:
```bash
# Check available Python versions
python3 --version
python3.8 --version
python3.9 --version

# Use specific Python version
curl -sSL https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh | PYTHON_CMD=python3.9 bash
```

### Network/Firewall Issues
**Problem**: Cannot download packages or connect to APIs

**Solutions**:
1. Check corporate firewall settings
2. Configure proxy settings if needed:
   ```bash
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   ```
3. Use alternative installation method (manual installation)

## Next Steps

After successful quick installation:

1. **[Configuration Guide](../configuration/)** - Detailed configuration options
2. **[Quick Start Tutorial](../usage/quick-start.md)** - Learn basic Nomad usage
3. **[Processing Modes](../usage/processing-modes/)** - Understand different modes
4. **[Integration Setup](../integrations/)** - Connect with other services

## Alternative Installation Methods

If the quick installation doesn't work for your environment:

- **[Manual Installation](manual-installation.md)** - Step-by-step pip installation
- **[Docker Installation](docker-installation.md)** - Containerized installation
- **[Development Setup](development-setup.md)** - Source code installation

## Need Help?

- **Installation Issues**: [Troubleshooting Guide](troubleshooting-installation.md)
- **Configuration Help**: [Configuration Documentation](../configuration/)
- **Community Support**: [GitHub Discussions](https://github.com/nomad-notion-automation/nomad/discussions)
- **Bug Reports**: [GitHub Issues](https://github.com/nomad-notion-automation/nomad/issues)

---

*Quick installation guide for Nomad v0.2.0. Updated: [Current Date]*