#!/bin/bash

# N0MAD Standalone Installation Script
# Installs N0MAD without requiring pip, creating a portable installation
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/ddcodepl/n0mad/master/install.sh | bash
#   or
#   wget -qO- https://raw.githubusercontent.com/ddcodepl/n0mad/master/install.sh | bash
#   or
#   bash install.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Configuration
N0MAD_VERSION="latest"
INSTALL_DIR="$HOME/.n0mad"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$INSTALL_DIR/venv"
SOURCE_DIR="$INSTALL_DIR/source"
REPO_URL="https://github.com/ddcodepl/n0mad"

# Function to print colored output
print_header() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${WHITE}                           N0MAD STANDALONE INSTALLER                           ${PURPLE}║${NC}"
    echo -e "${PURPLE}║${CYAN}        Notion Orchestrated Management & Autonomous Developer                 ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "cygwin" || "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Function to detect Linux distribution
detect_linux_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo $ID
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    else
        echo "unknown"
    fi
}

# Function to check Python version
check_python() {
    print_step "Checking Python installation..."

    local python_cmd=""
    local python_version=""

    # Try different Python commands
    for cmd in python3 python python3.11 python3.10 python3.9 python3.8; do
        if command_exists "$cmd"; then
            version=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            major=$(echo $version | cut -d. -f1)
            minor=$(echo $version | cut -d. -f2)

            if [ "$major" -eq 3 ] && [ "$minor" -ge 8 ]; then
                python_cmd="$cmd"
                python_version="$version"
                break
            fi
        fi
    done

    if [ -z "$python_cmd" ]; then
        print_error "Python 3.8+ is required but not found."
        print_status "Please install Python 3.8 or higher and try again."

        local os=$(detect_os)
        case $os in
            "linux")
                local distro=$(detect_linux_distro)
                case $distro in
                    "ubuntu"|"debian")
                        print_status "Install with: sudo apt update && sudo apt install python3 python3-venv python3-pip"
                        ;;
                    "fedora"|"rhel"|"centos")
                        print_status "Install with: sudo dnf install python3 python3-venv python3-pip"
                        ;;
                    "arch")
                        print_status "Install with: sudo pacman -S python python-pip"
                        ;;
                esac
                ;;
            "macos")
                print_status "Install with Homebrew: brew install python3"
                print_status "Or download from: https://www.python.org/downloads/"
                ;;
            "windows")
                print_status "Download from: https://www.python.org/downloads/"
                ;;
        esac
        exit 1
    fi

    print_success "Found Python $python_version at $(which $python_cmd)"
    echo "$python_cmd"
}

# Function to install system dependencies
install_system_deps() {
    local os=$(detect_os)

    print_step "Installing system dependencies..."

    case $os in
        "linux")
            local distro=$(detect_linux_distro)
            case $distro in
                "ubuntu"|"debian")
                    if ! command_exists git; then
                        print_status "Installing git..."
                        sudo apt update && sudo apt install -y git
                    fi
                    if ! command_exists curl; then
                        print_status "Installing curl..."
                        sudo apt install -y curl
                    fi
                    ;;
                "fedora"|"rhel"|"centos")
                    if ! command_exists git; then
                        print_status "Installing git..."
                        sudo dnf install -y git
                    fi
                    if ! command_exists curl; then
                        print_status "Installing curl..."
                        sudo dnf install -y curl
                    fi
                    ;;
                "arch")
                    if ! command_exists git; then
                        print_status "Installing git..."
                        sudo pacman -S --noconfirm git
                    fi
                    if ! command_exists curl; then
                        print_status "Installing curl..."
                        sudo pacman -S --noconfirm curl
                    fi
                    ;;
            esac
            ;;
        "macos")
            if ! command_exists git; then
                print_status "Please install Xcode Command Line Tools: xcode-select --install"
                exit 1
            fi
            ;;
    esac

    print_success "System dependencies ready"
}

# Function to create directories
create_directories() {
    print_step "Creating installation directories..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BIN_DIR"
    mkdir -p "$SOURCE_DIR"

    print_success "Directories created:"
    print_status "  Installation: $INSTALL_DIR"
    print_status "  Binaries: $BIN_DIR"
    print_status "  Source: $SOURCE_DIR"
}

# Function to download N0MAD source
download_source() {
    print_step "Downloading N0MAD source code..."

    if [ -d "$SOURCE_DIR/.git" ]; then
        print_status "Updating existing N0MAD installation..."
        cd "$SOURCE_DIR"
        git pull origin master
    else
        print_status "Cloning N0MAD repository..."
        rm -rf "$SOURCE_DIR"
        git clone "$REPO_URL.git" "$SOURCE_DIR"
        cd "$SOURCE_DIR"

        if [ "$N0MAD_VERSION" != "latest" ]; then
            print_status "Checking out version $N0MAD_VERSION..."
            git checkout "v$N0MAD_VERSION"
        fi
    fi

    print_success "Source code downloaded to $SOURCE_DIR"
}

# Function to create virtual environment
create_virtual_env() {
    local python_cmd=$1

    print_step "Creating Python virtual environment..."

    if [ -d "$VENV_DIR" ]; then
        print_status "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
    fi

    print_status "Creating new virtual environment with $python_cmd..."
    "$python_cmd" -m venv "$VENV_DIR"

    # Activate virtual environment
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    print_status "Upgrading pip..."
    "$VENV_DIR/bin/python" -m pip install --upgrade pip

    print_success "Virtual environment created at $VENV_DIR"
}

# Function to install N0MAD dependencies
install_dependencies() {
    print_step "Installing N0MAD dependencies..."

    # Activate virtual environment
    source "$VENV_DIR/bin/activate"

    cd "$SOURCE_DIR"

    # Install dependencies from pyproject.toml
    print_status "Installing core dependencies..."
    "$VENV_DIR/bin/python" -m pip install -e .

    print_success "Dependencies installed successfully"
}

# Function to create wrapper script
create_wrapper_script() {
    print_step "Creating N0MAD wrapper script..."

    local wrapper_script="$BIN_DIR/n0mad"

    cat > "$wrapper_script" << EOF
#!/bin/bash
# N0MAD Wrapper Script
# This script activates the N0MAD virtual environment and runs the command

# Activate N0MAD virtual environment
source "$VENV_DIR/bin/activate"

# Change to source directory
cd "$SOURCE_DIR"

# Run N0MAD with all arguments
exec "$VENV_DIR/bin/python" -m src.entry.main "\$@"
EOF

    chmod +x "$wrapper_script"

    # Also create nomad symlink for backwards compatibility
    ln -sf "$wrapper_script" "$BIN_DIR/nomad"

    print_success "Wrapper script created at $wrapper_script"
}

# Function to update PATH
update_path() {
    print_step "Updating PATH configuration..."

    local shell_profile=""
    local current_shell=$(basename "$SHELL")

    case $current_shell in
        "bash")
            if [ -f "$HOME/.bashrc" ]; then
                shell_profile="$HOME/.bashrc"
            elif [ -f "$HOME/.bash_profile" ]; then
                shell_profile="$HOME/.bash_profile"
            else
                shell_profile="$HOME/.profile"
            fi
            ;;
        "zsh")
            shell_profile="$HOME/.zshrc"
            ;;
        "fish")
            shell_profile="$HOME/.config/fish/config.fish"
            ;;
        *)
            shell_profile="$HOME/.profile"
            ;;
    esac

    # Check if PATH already contains our bin directory
    if ! echo "$PATH" | grep -q "$BIN_DIR"; then
        if [ "$current_shell" = "fish" ]; then
            echo "set -gx PATH $BIN_DIR \$PATH" >> "$shell_profile"
        else
            echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$shell_profile"
        fi

        print_success "Added $BIN_DIR to PATH in $shell_profile"
        print_warning "Please restart your terminal or run: source $shell_profile"
    else
        print_success "PATH already configured correctly"
    fi

    # Update current session PATH
    export PATH="$BIN_DIR:$PATH"
}

# Function to test installation
test_installation() {
    print_step "Testing N0MAD installation..."

    if [ -x "$BIN_DIR/n0mad" ]; then
        print_status "Testing n0mad command..."
        if "$BIN_DIR/n0mad" --version >/dev/null 2>&1; then
            local version_output=$("$BIN_DIR/n0mad" --version 2>&1)
            print_success "N0MAD is working! $version_output"
        else
            print_warning "N0MAD command exists but may have issues"
        fi
    else
        print_error "N0MAD command not found at $BIN_DIR/n0mad"
        return 1
    fi
}

# Function to create configuration template
create_config_template() {
    print_step "Creating configuration template..."

    local config_dir="$HOME/.n0mad"
    local config_file="$config_dir/config.env"

    mkdir -p "$config_dir"

    if [ ! -f "$config_file" ]; then
        cat > "$config_file" << EOF
# N0MAD Configuration File
# Copy this file and edit with your actual values

# Required: Notion Integration
NOTION_TOKEN=your_notion_integration_token_here
NOTION_BOARD_DB=your_notion_database_id_here

# Required: At least one AI provider API key
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional: N0MAD Configuration
NOMAD_HOME=$HOME/.n0mad
NOMAD_TASKS_DIR=./tasks
NOMAD_LOG_LEVEL=INFO
NOMAD_MAX_CONCURRENT_TASKS=3

# Optional: Global config file path
NOMAD_CONFIG_FILE=$config_file
EOF

        chmod 600 "$config_file"
        print_success "Configuration template created at $config_file"
        print_status "Edit this file with your API keys and settings"
    else
        print_success "Configuration file already exists at $config_file"
    fi
}

# Function to show completion message
show_completion() {
    print_header
    print_success "🎉 N0MAD installation completed successfully!"
    echo ""
    echo -e "${WHITE}📦 Installation Details:${NC}"
    echo -e "  ${CYAN}Installation Directory:${NC} $INSTALL_DIR"
    echo -e "  ${CYAN}Executable:${NC} $BIN_DIR/n0mad"
    echo -e "  ${CYAN}Configuration:${NC} $HOME/.n0mad/config.env"
    echo ""
    echo -e "${WHITE}🚀 Next Steps:${NC}"
    echo -e "  ${GREEN}1.${NC} ${CYAN}Configure your API keys:${NC}"
    echo -e "     ${YELLOW}edit $HOME/.n0mad/config.env${NC}"
    echo ""
    echo -e "  ${GREEN}2.${NC} ${CYAN}Test the installation:${NC}"
    echo -e "     ${YELLOW}n0mad --version${NC}"
    echo -e "     ${YELLOW}n0mad --config-status${NC}"
    echo ""
    echo -e "  ${GREEN}3.${NC} ${CYAN}Get help:${NC}"
    echo -e "     ${YELLOW}n0mad --help${NC}"
    echo -e "     ${YELLOW}n0mad --config-help${NC}"
    echo ""
    echo -e "${WHITE}📚 Documentation:${NC}"
    echo -e "  ${CYAN}GitHub:${NC} https://github.com/ddcodepl/n0mad"
    echo -e "  ${CYAN}Issues:${NC} https://github.com/ddcodepl/n0mad/issues"
    echo ""

    if ! echo "$PATH" | grep -q "$BIN_DIR"; then
        echo -e "${YELLOW}⚠️  Please restart your terminal or run:${NC}"
        echo -e "   ${WHITE}source ~/.bashrc${NC} (or your shell's profile file)"
        echo ""
    fi

    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${WHITE}                     Welcome to N0MAD - Happy Automating! 🤖                   ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
}

# Function to handle cleanup on error
cleanup_on_error() {
    print_error "Installation failed. Cleaning up..."
    if [ -d "$INSTALL_DIR" ]; then
        read -p "Remove installation directory $INSTALL_DIR? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
            print_status "Installation directory removed"
        fi
    fi
}

# Main installation function
main() {
    # Set up error handling
    trap cleanup_on_error ERR

    print_header

    print_status "🤖 Welcome to the N0MAD Standalone Installer!"
    print_status "This script will install N0MAD without requiring pip"
    echo ""

    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root. N0MAD will be installed system-wide."
        INSTALL_DIR="/opt/n0mad"
        BIN_DIR="/usr/local/bin"
        VENV_DIR="$INSTALL_DIR/venv"
        SOURCE_DIR="$INSTALL_DIR/source"
    fi

    # Installation steps
    local python_cmd=$(check_python)
    install_system_deps
    create_directories
    download_source
    create_virtual_env "$python_cmd"
    install_dependencies
    create_wrapper_script
    update_path
    test_installation
    create_config_template

    show_completion
}

# Run main function if script is executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
