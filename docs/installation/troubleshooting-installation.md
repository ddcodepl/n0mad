# Installation Troubleshooting Guide

This guide helps you resolve common installation issues with Nomad. If you encounter problems during installation, check this guide for solutions.

## Quick Diagnosis

Before diving into specific issues, run these commands to diagnose your installation:

```bash
# Check system requirements
python3 --version
pip3 --version
curl --version

# Check if Nomad is installed
nomad --version

# Check configuration status
nomad --config-status
```

## Common Installation Issues

### 1. Command Not Found Errors

#### Problem: `nomad: command not found`
This is the most common issue after installation.

**Symptoms**:
```bash
$ nomad --version
bash: nomad: command not found
```

**Causes**:
- Nomad installed to a directory not in PATH
- Shell hasn't been reloaded after installation
- Installation failed silently

**Solutions**:

1. **Check if Nomad is installed**:
   ```bash
   pip3 show nomad-notion-automation
   ```

2. **Find where Nomad is installed**:
   ```bash
   python3 -m pip show -f nomad-notion-automation | grep nomad
   find ~ -name "nomad" -type f 2>/dev/null
   ```

3. **Add to PATH temporarily**:
   ```bash
   export PATH=$PATH:~/.local/bin
   nomad --version
   ```

4. **Add to PATH permanently**:
   ```bash
   # For bash
   echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
   source ~/.bashrc

   # For zsh
   echo 'export PATH=$PATH:~/.local/bin' >> ~/.zshrc
   source ~/.zshrc
   ```

5. **Use full path**:
   ```bash
   ~/.local/bin/nomad --version
   ```

6. **Reinstall with user flag**:
   ```bash
   pip3 install --user nomad-notion-automation
   ```

### 2. Permission Errors

#### Problem: Permission denied during installation

**Symptoms**:
```bash
ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied
```

**Solutions**:

1. **Install to user directory**:
   ```bash
   pip3 install --user nomad-notion-automation
   ```

2. **Use virtual environment** (recommended):
   ```bash
   python3 -m venv nomad-env
   source nomad-env/bin/activate  # Windows: nomad-env\Scripts\activate
   pip install nomad-notion-automation
   ```

3. **Fix pip permissions** (Linux/macOS):
   ```bash
   sudo chown -R $(whoami) ~/.local
   pip3 install --user nomad-notion-automation
   ```

4. **Use sudo** (not recommended):
   ```bash
   sudo pip3 install nomad-notion-automation
   ```

### 3. Python Version Issues

#### Problem: Unsupported Python version

**Symptoms**:
```bash
ERROR: nomad-notion-automation requires Python '>=3.8' but the running Python is 3.7.x
```

**Solutions**:

1. **Check available Python versions**:
   ```bash
   python3 --version
   python3.8 --version
   python3.9 --version
   ```

2. **Install newer Python**:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3.9 python3.9-pip

   # macOS (using Homebrew)
   brew install python@3.9

   # CentOS/RHEL
   sudo yum install python39 python39-pip
   ```

3. **Use specific Python version**:
   ```bash
   python3.9 -m pip install nomad-notion-automation
   ```

4. **Use pyenv for Python version management**:
   ```bash
   # Install pyenv first, then:
   pyenv install 3.9.16
   pyenv global 3.9.16
   pip install nomad-notion-automation
   ```

### 4. Package Dependency Conflicts

#### Problem: Dependency version conflicts

**Symptoms**:
```bash
ERROR: nomad-notion-automation has requirement aiohttp>=3.9.0, but you have aiohttp 3.8.0
```

**Solutions**:

1. **Use virtual environment** (best solution):
   ```bash
   python3 -m venv clean-env
   source clean-env/bin/activate
   pip install nomad-notion-automation
   ```

2. **Upgrade conflicting packages**:
   ```bash
   pip install --upgrade aiohttp
   pip install nomad-notion-automation
   ```

3. **Force reinstall**:
   ```bash
   pip install --force-reinstall nomad-notion-automation
   ```

4. **Use pip-tools for dependency management**:
   ```bash
   pip install pip-tools
   pip-compile requirements.in
   pip-sync requirements.txt
   ```

### 5. Network and Firewall Issues

#### Problem: Cannot connect to PyPI or API endpoints

**Symptoms**:
```bash
ERROR: Could not find a version that satisfies the requirement nomad-notion-automation
WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None))
```

**Solutions**:

1. **Check internet connectivity**:
   ```bash
   ping pypi.org
   curl -I https://pypi.org
   ```

2. **Configure proxy settings**:
   ```bash
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=https://proxy.company.com:8080
   pip install nomad-notion-automation
   ```

3. **Use alternative PyPI mirrors**:
   ```bash
   pip install -i https://pypi.douban.com/simple/ nomad-notion-automation
   ```

4. **Disable SSL verification** (only if necessary):
   ```bash
   pip install --trusted-host pypi.org --trusted-host pypi.python.org nomad-notion-automation
   ```

5. **Download and install offline**:
   ```bash
   # On a machine with internet:
   pip download nomad-notion-automation

   # On the target machine:
   pip install nomad_notion_automation-*.whl
   ```

### 6. Docker Installation Issues

#### Problem: Docker container fails to start

**Solutions**:

1. **Check Docker daemon**:
   ```bash
   docker --version
   systemctl status docker  # Linux
   ```

2. **Build image manually**:
   ```bash
   git clone https://github.com/nomad-notion-automation/nomad.git
   cd nomad
   docker build -t nomad .
   ```

3. **Check environment variables**:
   ```bash
   docker run --env-file .env nomad --config-status
   ```

4. **Debug container**:
   ```bash
   docker run -it --entrypoint /bin/bash nomad
   ```

## Platform-Specific Issues

### Windows Issues

#### Problem: PowerShell execution policy

**Symptoms**:
```powershell
cannot be loaded because running scripts is disabled on this system
```

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Problem: Long path support

**Solution**:
Enable long path support in Windows:
1. Open Group Policy Editor (`gpedit.msc`)
2. Navigate to: Computer Configuration > Administrative Templates > System > Filesystem
3. Enable "Enable Win32 long paths"

### macOS Issues

#### Problem: Xcode Command Line Tools missing

**Symptoms**:
```bash
error: Microsoft Visual C++ 14.0 is required
xcrun: error: invalid active developer path
```

**Solution**:
```bash
xcode-select --install
```

#### Problem: SSL certificate errors

**Solution**:
```bash
# Update certificates
/Applications/Python\ 3.9/Install\ Certificates.command

# Or install certificates manually
pip install --upgrade certifi
```

### Linux Issues

#### Problem: Missing build essentials

**Symptoms**:
```bash
error: Microsoft Visual C++ 14.0 is required
gcc: command not found
```

**Solution**:
```bash
# Ubuntu/Debian
sudo apt install build-essential python3-dev

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
sudo yum install python3-devel

# Fedora
sudo dnf groupinstall "Development Tools"
sudo dnf install python3-devel
```

## Configuration Issues

### 1. API Key Problems

#### Problem: Invalid API key format

**Symptoms**:
```bash
⚠️  Notion token format appears invalid. Expected format: secret_...
❌ OpenAI API key configured but format issues: Invalid key format
```

**Solutions**:

1. **Verify API key formats**:
   - Notion: starts with `secret_`
   - OpenAI: starts with `sk-`
   - Anthropic: starts with `sk-ant-`
   - OpenRouter: starts with `sk-or-`

2. **Check for extra spaces or characters**:
   ```bash
   # Remove any extra whitespace
   NOTION_TOKEN=$(echo $NOTION_TOKEN | tr -d '[:space:]')
   ```

3. **Regenerate API keys** if format doesn't match

### 2. Configuration File Issues

#### Problem: Configuration file not found

**Solutions**:

1. **Create configuration file**:
   ```bash
   nomad --config-create
   ```

2. **Set configuration file path**:
   ```bash
   export NOMAD_CONFIG_FILE=~/.nomad/config.env
   ```

3. **Check file permissions**:
   ```bash
   chmod 600 ~/.nomad/config.env
   ```

## Verification and Testing

### Complete Installation Test

Run this comprehensive test to verify your installation:

```bash
#!/bin/bash
echo "🔍 Nomad Installation Verification"
echo "=================================="

# Check Python
echo "Python version:"
python3 --version || echo "❌ Python 3 not found"

# Check pip
echo "Pip version:"
python3 -m pip --version || echo "❌ Pip not found"

# Check Nomad installation
echo "Nomad installation:"
pip3 show nomad-notion-automation || echo "❌ Nomad not installed"

# Check Nomad command
echo "Nomad command:"
nomad --version || echo "❌ Nomad command not found"

# Check configuration
echo "Configuration status:"
nomad --config-status

# Check health
echo "Health check:"
nomad --health-check

echo "✅ Verification complete"
```

Save this as `verify-installation.sh` and run:
```bash
chmod +x verify-installation.sh
./verify-installation.sh
```

## Getting Additional Help

### Diagnostic Information

When asking for help, include this diagnostic information:

```bash
# System information
uname -a
python3 --version
pip3 --version

# Nomad information
pip3 show nomad-notion-automation
nomad --version 2>&1 || echo "Command not found"
nomad --config-status 2>&1 || echo "Cannot run config check"

# Environment
echo $PATH
echo $PYTHONPATH
which python3
which pip3
```

### Where to Get Help

1. **Documentation**:
   - [Installation Guide](README.md)
   - [Configuration Guide](../configuration/)
   - [System Requirements](system-requirements.md)

2. **Community Support**:
   - [GitHub Discussions](https://github.com/nomad-notion-automation/nomad/discussions)
   - [Discord Community](https://discord.gg/nomad) (if available)

3. **Issue Reporting**:
   - [GitHub Issues](https://github.com/nomad-notion-automation/nomad/issues)
   - Include diagnostic information
   - Describe steps to reproduce

4. **Professional Support**:
   - Enterprise support available
   - Custom installation assistance
   - Priority issue resolution

### Creating a Bug Report

When filing an issue, include:

1. **System Information**:
   - Operating system and version
   - Python version
   - Installation method used

2. **Error Details**:
   - Complete error messages
   - Commands that failed
   - Expected vs. actual behavior

3. **Environment**:
   - Virtual environment usage
   - Proxy or firewall settings
   - Other relevant software

4. **Steps to Reproduce**:
   - Exact commands run
   - Configuration used
   - Any customizations made

## Prevention Tips

### Best Practices for Installation

1. **Use Virtual Environments**:
   ```bash
   python3 -m venv nomad-env
   source nomad-env/bin/activate
   pip install nomad-notion-automation
   ```

2. **Keep Systems Updated**:
   ```bash
   # Update package managers
   pip install --upgrade pip setuptools wheel

   # Update system packages regularly
   sudo apt update && sudo apt upgrade  # Ubuntu/Debian
   brew update && brew upgrade          # macOS
   ```

3. **Backup Configurations**:
   ```bash
   cp ~/.nomad/config.env ~/.nomad/config.env.backup
   ```

4. **Monitor System Resources**:
   ```bash
   df -h      # Check disk space
   free -h    # Check memory
   ```

5. **Use Stable Versions**:
   ```bash
   pip install nomad-notion-automation==0.2.0  # Pin to specific version
   ```

---

*Installation troubleshooting guide for Nomad v0.2.0. If your issue isn't covered here, please [file an issue](https://github.com/nomad-notion-automation/nomad/issues).*
