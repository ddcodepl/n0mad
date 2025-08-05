#!/bin/bash

# Nomad Global Installation Script
# Installs nomad-notion-automation package globally with pip

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python() {
    if command_exists python3; then
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    elif command_exists python; then
        PYTHON_CMD="python"
        PIP_CMD="pip"
    else
        print_error "Python is not installed. Please install Python 3.8 or higher."
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info[0])")
    PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info[1])")
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        print_error "Python 3.8 or higher is required. Found Python $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION found"
}

# Function to install package
install_package() {
    print_status "Installing nomad-notion-automation package..."
    
    # Check if we're in a virtual environment
    if [[ -n "$VIRTUAL_ENV" ]]; then
        print_warning "Installing in virtual environment: $VIRTUAL_ENV"
    else
        print_status "Installing globally (use --user if you don't have sudo access)"
    fi
    
    # Install from local directory if we're in the source directory
    if [[ -f "pyproject.toml" && -f "entry/main.py" ]]; then
        print_status "Installing from local source directory..."
        if [[ -n "$VIRTUAL_ENV" ]]; then
            $PIP_CMD install -e .
        else
            $PIP_CMD install -e . --user
        fi
    else
        # Install from package (would be from PyPI in real deployment)
        print_status "Installing from package..."
        if [[ -n "$VIRTUAL_ENV" ]]; then
            $PIP_CMD install nomad-notion-automation
        else
            $PIP_CMD install nomad-notion-automation --user
        fi
    fi
}

# Function to verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    if command_exists nomad; then
        print_success "nomad command is available"
        
        # Test basic functionality
        NOMAD_VERSION=$(nomad --version 2>/dev/null || echo "Version check failed")
        print_status "Version: $NOMAD_VERSION"
        
        # Test configuration system
        print_status "Testing configuration system..."
        nomad --config-help >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            print_success "Configuration system working"
        else
            print_warning "Configuration system test failed (this is expected without API keys)"
        fi
        
    else
        print_error "nomad command not found in PATH"
        print_status "You may need to:"
        echo "  1. Restart your terminal"
        echo "  2. Add ~/.local/bin to your PATH"
        echo "  3. Run: export PATH=\$PATH:~/.local/bin"
        return 1
    fi
}

# Function to setup configuration
setup_configuration() {
    print_status "Setting up configuration..."
    
    # Create config template
    nomad --config-create 2>/dev/null || {
        print_warning "Could not create config template automatically"
        print_status "You can create it manually later with: nomad --config-create"
    }
    
    print_status "Configuration setup complete"
    print_status "Edit your configuration file and set your API keys"
    print_status "Then run: nomad --config-status"
}

# Function to show post-installation instructions
show_instructions() {
    print_success "Installation completed successfully!"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 Nomad is now installed globally!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo "📋 Next steps:"
    echo "  1. Configure your API keys:"
    echo "     nomad --config-help"
    echo
    echo "  2. Create configuration template:"
    echo "     nomad --config-create"
    echo
    echo "  3. Check configuration status:"
    echo "     nomad --config-status"
    echo
    echo "  4. Get help:"
    echo "     nomad --help"
    echo
    echo "🔧 Required API Keys:"
    echo "  • NOTION_TOKEN (required) - Your Notion integration token"
    echo "  • NOTION_BOARD_DB (required) - Your Notion database ID"
    echo "  • At least one AI provider key:"
    echo "    - OPENAI_API_KEY (OpenAI)"
    echo "    - OPENROUTER_API_KEY (OpenRouter)"
    echo "    - ANTHROPIC_API_KEY (Anthropic)"
    echo
    echo "📚 Documentation: https://github.com/nomad-notion-automation/nomad"
    echo "🐛 Issues: https://github.com/nomad-notion-automation/nomad/issues"
    echo
}

# Main installation process
main() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 Nomad Global Installation Script"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    
    # Check system requirements
    print_status "Checking system requirements..."
    check_python
    
    # Check if pip is available
    if ! command_exists $PIP_CMD; then
        print_error "pip is not installed. Please install pip first."
        exit 1
    fi
    
    print_success "System requirements met"
    echo
    
    # Install package
    install_package
    echo
    
    # Verify installation
    verify_installation
    echo
    
    # Setup configuration
    setup_configuration
    echo
    
    # Show post-installation instructions
    show_instructions
}

# Parse command line arguments
SKIP_VERIFICATION=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-verification)
            SKIP_VERIFICATION=true
            shift
            ;;
        --help)
            echo "Nomad Installation Script"
            echo
            echo "Usage: $0 [options]"
            echo
            echo "Options:"
            echo "  --skip-verification  Skip installation verification"
            echo "  --help              Show this help message"
            echo
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main installation
main

exit 0