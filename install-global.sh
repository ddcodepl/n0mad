#!/bin/bash

# N0MAD Global Installation Script
# Installs N0MAD globally using pipx or pip with virtual environment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

print_header() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${GREEN}                           N0MAD GLOBAL INSTALLER                              ${PURPLE}║${NC}"
    echo -e "${PURPLE}║${BLUE}        Notion Orchestrated Management & Autonomous Developer                 ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python
check_python() {
    for cmd in python3 python; do
        if command_exists "$cmd"; then
            version=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            major=$(echo $version | cut -d. -f1)
            minor=$(echo $version | cut -d. -f2)
            
            if [ "$major" -eq 3 ] && [ "$minor" -ge 8 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

install_with_pipx() {
    print_status "Installing N0MAD with pipx (recommended)..."
    if ! command_exists pipx; then
        print_status "Installing pipx first..."
        "$python_cmd" -m pip install --user pipx
        "$python_cmd" -m pipx ensurepath
    fi
    
    # Install from local source
    pipx install .
    print_success "N0MAD installed globally with pipx"
}

install_with_pip_user() {
    print_status "Installing N0MAD with pip --user..."
    "$python_cmd" -m pip install --user .
    print_success "N0MAD installed in user space"
}

main() {
    print_header
    
    print_status "🚀 Installing N0MAD globally..."
    
    # Check if we're in the source directory
    if [ ! -f "pyproject.toml" ] || [ ! -f "setup.py" ]; then
        print_error "This script must be run from the N0MAD source directory"
        print_status "Please cd to the N0MAD directory and run: bash install-global.sh"
        exit 1
    fi
    
    # Check Python
    if ! python_cmd=$(check_python); then
        print_error "Python 3.8+ is required but not found"
        exit 1
    fi
    
    print_success "Found Python at $(which $python_cmd)"
    
    # Try different installation methods
    if command_exists pipx; then
        install_with_pipx
    else
        print_status "pipx not found, trying pip --user..."
        install_with_pip_user
    fi
    
    print_success "🎉 N0MAD installation completed!"
    print_status "You can now use: n0mad --help"
    print_status "Configure with: n0mad --config-help"
}

main "$@"