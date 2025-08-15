#!/bin/bash

# N0MAD Uninstaller Script
# Removes N0MAD standalone installation

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configuration
INSTALL_DIR="$HOME/.n0mad"
BIN_DIR="$HOME/.local/bin"

print_header() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${RED}                           N0MAD UNINSTALLER                                 ${PURPLE}║${NC}"
    echo -e "${PURPLE}║${YELLOW}        Removes N0MAD standalone installation                               ${PURPLE}║${NC}"
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

# Function to prompt user
prompt_user() {
    local message="$1"
    local default="${2:-n}"

    if [ "$default" = "y" ]; then
        read -p "$message [Y/n] " -n 1 -r
    else
        read -p "$message [y/N] " -n 1 -r
    fi
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to remove installation directory
remove_installation() {
    if [ -d "$INSTALL_DIR" ]; then
        print_status "Found N0MAD installation at $INSTALL_DIR"

        if prompt_user "Remove N0MAD installation directory?"; then
            rm -rf "$INSTALL_DIR"
            print_success "Installation directory removed"
        else
            print_warning "Installation directory kept"
        fi
    else
        print_status "No installation directory found at $INSTALL_DIR"
    fi
}

# Function to remove executables
remove_executables() {
    local removed_any=false

    for cmd in n0mad nomad; do
        local exe_path="$BIN_DIR/$cmd"
        if [ -f "$exe_path" ] || [ -L "$exe_path" ]; then
            print_status "Found executable: $exe_path"
            rm -f "$exe_path"
            print_success "Removed $cmd command"
            removed_any=true
        fi
    done

    if [ "$removed_any" = false ]; then
        print_status "No N0MAD executables found in $BIN_DIR"
    fi
}

# Function to clean PATH
clean_path() {
    local shell_profiles=(
        "$HOME/.bashrc"
        "$HOME/.bash_profile"
        "$HOME/.zshrc"
        "$HOME/.profile"
        "$HOME/.config/fish/config.fish"
    )

    local cleaned_any=false

    for profile in "${shell_profiles[@]}"; do
        if [ -f "$profile" ]; then
            # Check if file contains our PATH modification
            if grep -q "$BIN_DIR" "$profile"; then
                print_status "Found PATH entry in $profile"

                if prompt_user "Remove PATH entry from $profile?"; then
                    # Create backup
                    cp "$profile" "$profile.n0mad-backup"

                    # Remove lines containing our bin directory
                    if command -v sed >/dev/null 2>&1; then
                        sed -i.bak "/$(echo "$BIN_DIR" | sed 's/[[\.*^$()+?{|]/\\&/g')/d" "$profile"
                        rm -f "$profile.bak"
                    else
                        grep -v "$BIN_DIR" "$profile" > "$profile.tmp" && mv "$profile.tmp" "$profile"
                    fi

                    print_success "PATH entry removed from $profile"
                    print_status "Backup saved as $profile.n0mad-backup"
                    cleaned_any=true
                fi
            fi
        fi
    done

    if [ "$cleaned_any" = false ]; then
        print_status "No PATH entries found to clean"
    fi
}

# Function to remove configuration
remove_config() {
    local config_file="$HOME/.n0mad/config.env"

    if [ -f "$config_file" ]; then
        print_status "Found configuration file: $config_file"
        print_warning "This contains your API keys and settings"

        if prompt_user "Remove configuration file? (Contains API keys)"; then
            rm -f "$config_file"
            print_success "Configuration file removed"
        else
            print_warning "Configuration file kept"
        fi
    else
        print_status "No configuration file found"
    fi
}

# Function to show completion
show_completion() {
    echo ""
    print_success "🗑️  N0MAD uninstallation completed!"
    echo ""
    print_status "What was removed:"
    print_status "  ✓ N0MAD executables from $BIN_DIR"
    print_status "  ✓ Installation directory (if selected)"
    print_status "  ✓ PATH entries (if selected)"
    print_status "  ✓ Configuration file (if selected)"
    echo ""
    print_status "If you want to reinstall N0MAD later:"
    print_status "  curl -sSL https://raw.githubusercontent.com/ddcodepl/n0mad/master/quick-install.sh | bash"
    echo ""
    print_status "Thank you for using N0MAD! 🤖"
}

# Main uninstall function
main() {
    print_header

    print_warning "This will remove N0MAD from your system"
    print_status "The following locations will be checked:"
    print_status "  • Installation: $INSTALL_DIR"
    print_status "  • Executables: $BIN_DIR/{n0mad,nomad}"
    print_status "  • Configuration: $HOME/.n0mad/config.env"
    print_status "  • PATH entries in shell profiles"
    echo ""

    if ! prompt_user "Continue with uninstallation?"; then
        print_status "Uninstallation cancelled"
        exit 0
    fi

    echo ""

    # Uninstall steps
    remove_executables
    remove_installation
    clean_path
    remove_config

    show_completion
}

# Run main function if script is executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
