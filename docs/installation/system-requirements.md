# System Requirements

This document outlines the system requirements and prerequisites for installing and running Nomad successfully.

## Overview

Nomad is designed to be lightweight and run on a variety of systems. However, certain minimum requirements must be met for optimal performance and functionality.

## Operating System Support

### Fully Supported
- **macOS**: 10.14 (Mojave) and later
- **Linux**: Most distributions with Python 3.8+
  - Ubuntu 18.04 LTS and later
  - Debian 10 and later
  - CentOS 7 and later
  - Fedora 30 and later
  - Arch Linux (current)
- **Windows**: Windows 10 and later with WSL2

### Limited Support
- **Windows Native**: Windows 10/11 (some features may be limited)
- **Docker**: Any platform supporting Docker

### Not Supported
- Windows 7 and earlier
- macOS 10.13 and earlier
- Python 2.x environments

## Hardware Requirements

### Minimum Requirements
| Component | Requirement | Notes |
|-----------|-------------|-------|
| **CPU** | 1 core, 1GHz+ | Single-threaded performance matters |
| **Memory** | 512 MB RAM | For basic task processing |
| **Storage** | 100 MB free space | For application and basic data |
| **Network** | Internet connectivity | Required for API calls |

### Recommended Requirements
| Component | Requirement | Notes |
|-----------|-------------|-------|
| **CPU** | 2+ cores, 2GHz+ | Better for concurrent processing |
| **Memory** | 1 GB+ RAM | Improved performance with multiple tasks |
| **Storage** | 500 MB+ free space | For logs, task files, and backups |
| **Network** | Stable broadband | Faster API responses |

### Performance Scaling
| Use Case | CPU | Memory | Notes |
|----------|-----|--------|-------|
| **Light Usage** | 1-2 cores | 512MB | <10 tasks/hour |
| **Regular Usage** | 2-4 cores | 1GB | 10-100 tasks/hour |
| **Heavy Usage** | 4+ cores | 2GB+ | 100+ tasks/hour |
| **Enterprise** | 8+ cores | 4GB+ | Continuous processing |

## Software Dependencies

### Python Requirements
- **Version**: Python 3.8.1 or higher
- **Recommended**: Python 3.9 or 3.10
- **Package Manager**: pip 20.0 or higher

#### Python Version Compatibility
| Python Version | Support Status | Notes |
|----------------|----------------|-------|
| 3.12 | ✅ Full Support | Latest features |
| 3.11 | ✅ Full Support | Recommended |
| 3.10 | ✅ Full Support | Recommended |
| 3.9 | ✅ Full Support | Stable |
| 3.8 | ✅ Full Support | Minimum version |
| 3.7 | ❌ Not Supported | End of life |
| 2.7 | ❌ Not Supported | Legacy |

### Required Python Packages
These packages are automatically installed with Nomad:

| Package | Version | Purpose |
|---------|---------|---------|
| `aiohttp` | >=3.9.0 | Async HTTP client for API calls |
| `notion-client` | >=2.2.1 | Notion API integration |
| `openai` | >=1.35.0 | OpenAI API client |
| `psutil` | >=7.0.0 | System monitoring and performance |
| `python-dotenv` | >=1.0.1 | Environment variable management |

### Optional Dependencies
For enhanced functionality:

| Package | Purpose | Installation |
|---------|---------|--------------|
| `pytest` | Testing framework | `pip install nomad[dev]` |
| `black` | Code formatting | `pip install nomad[dev]` |
| `isort` | Import sorting | `pip install nomad[dev]` |
| `mypy` | Type checking | `pip install nomad[dev]` |

### System Dependencies

#### Linux Systems
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip curl git

# CentOS/RHEL/Fedora
sudo yum install python3 python3-pip curl git
# or for newer versions:
sudo dnf install python3 python3-pip curl git

# Arch Linux
sudo pacman -S python python-pip curl git
```

#### macOS Systems
```bash
# Using Homebrew (recommended)
brew install python curl git

# Using MacPorts
sudo port install python39 curl git

# Xcode Command Line Tools (may be required)
xcode-select --install
```

#### Windows Systems
- **Python**: Download from [python.org](https://python.org) or Microsoft Store
- **Git**: Download from [git-scm.com](https://git-scm.com)
- **WSL2**: Recommended for best compatibility

## Network Requirements

### Internet Connectivity
- **Required**: Stable internet connection
- **Bandwidth**: Minimum 1 Mbps for API calls
- **Latency**: <500ms to API endpoints for optimal performance

### API Endpoints
Nomad needs access to these external services:

| Service | Endpoint | Purpose | Required |
|---------|----------|---------|----------|
| Notion API | `api.notion.com` | Task management | Yes |
| OpenAI API | `api.openai.com` | AI processing | Optional* |
| Anthropic API | `api.anthropic.com` | AI processing | Optional* |
| OpenRouter API | `openrouter.ai` | AI processing | Optional* |
| PyPI | `pypi.org` | Package installation | Installation only |

*At least one AI provider is required for full functionality.

### Firewall Considerations
Ensure outbound HTTPS (port 443) access to:
- `api.notion.com`
- `api.openai.com`
- `api.anthropic.com`
- `openrouter.ai`
- `pypi.org` (for installation)

### Proxy Support
If behind a corporate proxy:
```bash
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export NO_PROXY=localhost,127.0.0.1
```

## Storage Requirements

### Disk Space
| Component | Size | Location | Notes |
|-----------|------|----------|-------|
| **Application** | ~50 MB | Installation directory | Core application files |
| **Dependencies** | ~30 MB | Python site-packages | Required Python packages |
| **Configuration** | <1 MB | `~/.nomad/` | Configuration files |
| **Task Files** | Variable | `~/.nomad/tasks/` | Depends on usage |
| **Logs** | Variable | `~/.nomad/logs/` | Rotated automatically |
| **Backups** | Variable | `~/.nomad/backups/` | Task file backups |

### Estimated Total Usage
- **Minimal Setup**: ~100 MB
- **Typical Usage**: ~200-500 MB
- **Heavy Usage**: ~1-2 GB

### File System Permissions
Nomad needs read/write access to:
- Installation directory (typically `~/.local/` or `/usr/local/`)
- Configuration directory (`~/.nomad/`)
- Working directories where you run Nomad
- Temporary directory (`/tmp` or equivalent)

## Performance Considerations

### CPU Usage
- **Idle**: <1% CPU usage
- **Processing**: 10-50% CPU per concurrent task
- **AI Calls**: Low CPU, mostly I/O bound

### Memory Usage
- **Base**: ~50-100 MB
- **Per Task**: ~10-20 MB additional
- **Peak**: May temporarily spike during large operations

### Concurrent Processing
Default configuration allows 3 concurrent tasks. This can be adjusted based on system capabilities:

```env
# Adjust based on your system
NOMAD_MAX_CONCURRENT_TASKS=5  # For 4+ core systems
NOMAD_MAX_CONCURRENT_TASKS=1  # For single-core systems
```

### Monitoring Resource Usage
```bash
# Check Nomad resource usage
nomad --health-check

# Monitor system resources
top | grep nomad
ps aux | grep nomad
```

## Development Requirements

Additional requirements for development and testing:

### Development Tools
- **Git**: Version control
- **Make**: Build automation (optional)
- **Docker**: Container testing (optional)

### Testing Requirements
- **pytest**: Testing framework
- **pytest-asyncio**: Async testing support
- **pytest-cov**: Coverage reporting

### IDE/Editor Support
Nomad works well with:
- **VS Code**: With Python extension
- **PyCharm**: Professional or Community
- **Vim/Neovim**: With appropriate plugins
- **Emacs**: With Python mode

## Cloud Platform Requirements

### AWS
- **Instance Type**: t3.micro or larger
- **Storage**: 8 GB+ EBS volume
- **Security Groups**: Allow outbound HTTPS

### Google Cloud Platform
- **Machine Type**: e2-micro or larger
- **Disk**: 10 GB+ persistent disk
- **Firewall**: Allow outbound HTTPS

### Azure
- **VM Size**: B1s or larger
- **Storage**: 8 GB+ managed disk
- **Network**: Allow outbound HTTPS

### Docker Requirements
- **Docker Engine**: 19.03 or later
- **Memory**: 512 MB+ container limit
- **Storage**: 1 GB+ for image and volumes

## Validation Commands

Use these commands to verify system requirements:

```bash
# Check Python version
python3 --version

# Check pip version
python3 -m pip --version

# Check available memory
free -h  # Linux
vm_stat | head -10  # macOS
systeminfo | findstr Memory  # Windows

# Check disk space
df -h  # Linux/macOS
dir  # Windows

# Check network connectivity
ping -c 3 api.notion.com
curl -I https://api.openai.com

# Check system performance
nomad --health-check  # After installation
```

## Troubleshooting Requirements Issues

### Common Problems

#### Insufficient Memory
**Symptoms**: Slow performance, crashes, out of memory errors
**Solutions**:
- Reduce concurrent task limit
- Close other applications
- Add swap space (Linux)
- Upgrade system memory

#### Slow Network
**Symptoms**: Timeouts, slow API responses
**Solutions**:
- Check internet connection speed
- Configure proxy settings
- Reduce concurrent operations
- Consider local caching

#### Python Version Issues
**Symptoms**: Installation fails, import errors
**Solutions**:
- Install Python 3.8+
- Use virtual environments
- Check PATH configuration
- Use specific Python version commands

#### Permission Problems
**Symptoms**: Cannot write files, installation fails
**Solutions**:
- Use `--user` flag for pip install
- Fix directory permissions
- Use virtual environment
- Check disk space

## Getting Help

If you encounter issues with system requirements:

1. **Check Prerequisites**: Use validation commands above
2. **Review Error Messages**: Look for specific requirement failures
3. **Consult Documentation**: Check relevant installation guides
4. **Community Support**: Ask in [GitHub Discussions](https://github.com/nomad-notion-automation/nomad/discussions)
5. **Report Issues**: File a [GitHub Issue](https://github.com/nomad-notion-automation/nomad/issues) if requirements seem incorrect

---

*System requirements for Nomad v0.2.0. Requirements may change with future versions.*