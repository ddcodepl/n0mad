# 🚀 N0MAD Standalone Installation

This document describes how to install N0MAD without using pip, creating a completely self-contained installation.

## 🎯 Quick Installation

### One-Line Install

```bash
curl -sSL https://raw.githubusercontent.com/ddcodepl/n0mad/master/quick-install.sh | bash
```

**Alternative with wget:**
```bash
wget -qO- https://raw.githubusercontent.com/ddcodepl/n0mad/master/quick-install.sh | bash
```

### Manual Installation

1. **Download the installer:**
   ```bash
   curl -sSL https://raw.githubusercontent.com/ddcodepl/n0mad/master/install.sh -o install.sh
   chmod +x install.sh
   ```

2. **Run the installer:**
   ```bash
   ./install.sh
   ```

## 📋 What It Does

The standalone installer creates a completely self-contained N0MAD installation:

### 🏗️ Installation Process

1. **🔍 System Check**: Detects OS, Python version, and required tools
2. **📦 Dependencies**: Installs git and curl if needed (with sudo)
3. **📁 Directories**: Creates `~/.n0mad/` installation directory
4. **📥 Source Code**: Clones latest N0MAD from GitHub
5. **🐍 Virtual Environment**: Creates isolated Python environment
6. **⚡ Dependencies**: Installs all required Python packages
7. **🔗 Wrapper Script**: Creates `n0mad` command in `~/.local/bin/`
8. **🛣️ PATH Setup**: Adds executable to system PATH
9. **⚙️ Configuration**: Creates config template with API key placeholders

### 📂 Installation Structure

```
~/.n0mad/                     # Main installation directory
├── source/                   # N0MAD source code (git clone)
├── venv/                     # Python virtual environment
│   ├── bin/python           # Isolated Python interpreter
│   └── lib/python3.x/       # Isolated packages
└── config.env               # Configuration file

~/.local/bin/
├── n0mad                     # Main executable wrapper
└── nomad                     # Backwards compatibility symlink
```

## 🔧 Requirements

### System Requirements

- **Python 3.8+** (automatically detected)
- **Git** (installed automatically if missing)
- **curl or wget** (installed automatically if missing)
- **Internet connection** (for downloading)

### Supported Operating Systems

- ✅ **Linux** (Ubuntu, Debian, Fedora, CentOS, Arch)
- ✅ **macOS** (Intel and Apple Silicon)
- ✅ **Windows** (via WSL, Git Bash, or Cygwin)

## ⚙️ Configuration

### After Installation

1. **Edit configuration file:**
   ```bash
   nano ~/.n0mad/config.env
   ```

2. **Add your API keys:**
   ```bash
   # Required
   NOTION_TOKEN=your_notion_integration_token
   NOTION_BOARD_DB=your_notion_database_id

   # At least one AI provider
   OPENAI_API_KEY=your_openai_key
   ANTHROPIC_API_KEY=your_anthropic_key
   OPENROUTER_API_KEY=your_openrouter_key
   ```

3. **Test the installation:**
   ```bash
   n0mad --version
   n0mad --config-status
   ```

### Environment Variables

The installer creates a template with all available options:

```bash
# Core Configuration
NOMAD_HOME=~/.n0mad
NOMAD_TASKS_DIR=./tasks
NOMAD_LOG_LEVEL=INFO
NOMAD_MAX_CONCURRENT_TASKS=3

# Global config file
NOMAD_CONFIG_FILE=~/.n0mad/config.env
```

## 🎮 Usage

### Basic Commands

```bash
# Show version
n0mad --version

# Configuration management
n0mad --config-help
n0mad --config-status

# Task processing
n0mad --refine          # Process 'To Refine' tasks
n0mad --prepare         # Process 'Prepare Tasks'
n0mad --queued          # Process 'Queued to run' tasks
n0mad --multi           # Multi-status mode

# Get help
n0mad --help
```

### Backwards Compatibility

The installer also creates a `nomad` symlink for backwards compatibility:

```bash
nomad --version         # Same as n0mad --version
nomad --help           # Same as n0mad --help
```

## 🔄 Updates

### Automatic Updates

Re-run the installer to update to the latest version:

```bash
curl -sSL https://raw.githubusercontent.com/ddcodepl/n0mad/master/quick-install.sh | bash
```

The installer will:
- Pull latest source code from GitHub
- Recreate the virtual environment
- Update all dependencies
- Keep your existing configuration

### Manual Updates

```bash
cd ~/.n0mad/source
git pull origin master
source ~/.n0mad/venv/bin/activate
pip install -e .
```

## 🗑️ Uninstallation

### Quick Uninstall

```bash
curl -sSL https://raw.githubusercontent.com/ddcodepl/n0mad/master/uninstall.sh | bash
```

### Manual Uninstall

```bash
# Remove executables
rm -f ~/.local/bin/n0mad ~/.local/bin/nomad

# Remove installation directory
rm -rf ~/.n0mad

# Clean PATH (edit your shell profile)
nano ~/.bashrc  # or ~/.zshrc, ~/.profile
# Remove the line: export PATH="$HOME/.local/bin:$PATH"
```

The uninstaller will:
- Remove all N0MAD executables
- Optionally remove installation directory
- Optionally clean PATH entries from shell profiles
- Optionally remove configuration (with API keys)

## 🔧 Troubleshooting

### Installation Issues

#### Python Not Found
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3 python3-venv python3-pip

# Fedora/CentOS
sudo dnf install python3 python3-venv python3-pip

# macOS (Homebrew)
brew install python3

# Check Python version
python3 --version  # Should be 3.8+
```

#### Git Not Found
```bash
# Ubuntu/Debian
sudo apt install git

# Fedora/CentOS
sudo dnf install git

# macOS
xcode-select --install
```

#### Permission Issues
```bash
# Don't run with sudo - install in user space
./setup.sh

# If ~/.local/bin is not in PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Runtime Issues

#### Command Not Found
```bash
# Check if executable exists
ls -la ~/.local/bin/n0mad

# Check PATH
echo $PATH | grep -o ~/.local/bin

# Add to PATH temporarily
export PATH="$HOME/.local/bin:$PATH"

# Add to PATH permanently
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### Configuration Issues
```bash
# Check configuration status
n0mad --config-status

# Create new configuration template
n0mad --config-create

# Test with minimal config
NOTION_TOKEN=test_token NOTION_BOARD_DB=test_db n0mad --version
```

### Debug Mode

Enable verbose output for troubleshooting:

```bash
# Run installer with debug output
bash -x setup.sh

# Run N0MAD with debug logging
NOMAD_LOG_LEVEL=DEBUG n0mad --config-status
```

## 🆚 Standalone vs Pip Installation

| Feature | Standalone | Pip Install |
|---------|------------|-------------|
| **Installation** | One command | `pip install n0mad` |
| **Dependencies** | Self-contained | System Python |
| **Updates** | Re-run installer | `pip install -U n0mad` |
| **Isolation** | Complete isolation | Shares system packages |
| **Portability** | Fully portable | Depends on system |
| **Disk Space** | ~200MB | ~50MB |
| **Performance** | Same | Same |

### When to Use Standalone

- ✅ No pip available or restricted
- ✅ Want complete isolation
- ✅ Don't want to affect system Python
- ✅ Need portable installation
- ✅ Corporate environments with restrictions

### When to Use Pip

- ✅ Have pip available
- ✅ Want minimal disk usage
- ✅ Already managing Python packages
- ✅ Integration with existing environments

## 🔐 Security Considerations

### Installation Security

- ✅ **User Space**: Installs in `~/.n0mad/` (no sudo required)
- ✅ **Isolated Environment**: Uses virtual environment
- ✅ **Source Verification**: Downloads from official GitHub repository
- ✅ **Configuration Security**: Config file has restricted permissions (600)

### Best Practices

1. **Verify Source**: Always download from official repository
2. **Review Scripts**: Check installer content before running
3. **Secure Config**: Keep API keys in config file, not environment
4. **Regular Updates**: Update regularly for security patches
5. **Backup Config**: Save configuration before updates

## 📊 Installation Logs

The installer provides detailed progress information:

```bash
╔══════════════════════════════════════════════════════════════════════════════╗
║                           N0MAD STANDALONE INSTALLER                           ║
║        Notion Orchestrated Management & Autonomous Developer                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

[STEP] Checking Python installation...
[SUCCESS] Found Python 3.11.5 at /usr/bin/python3
[STEP] Installing system dependencies...
[SUCCESS] System dependencies ready
[STEP] Creating installation directories...
[SUCCESS] Directories created
[STEP] Downloading N0MAD source code...
[SUCCESS] Source code downloaded
[STEP] Creating Python virtual environment...
[SUCCESS] Virtual environment created
[STEP] Installing N0MAD dependencies...
[SUCCESS] Dependencies installed successfully
[STEP] Creating N0MAD wrapper script...
[SUCCESS] Wrapper script created
[STEP] Updating PATH configuration...
[SUCCESS] Added ~/.local/bin to PATH
[STEP] Testing N0MAD installation...
[SUCCESS] N0MAD is working! N0MAD v0.0.1
[STEP] Creating configuration template...
[SUCCESS] Configuration template created

🎉 N0MAD installation completed successfully!
```

---

**Ready to automate with N0MAD! 🤖**

*For more information, visit: https://github.com/ddcodepl/n0mad*
