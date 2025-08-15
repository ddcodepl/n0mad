#!/bin/bash

# N0MAD Quick Install Script
# Downloads and runs the main installer

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
    echo -e "${PURPLE}║${GREEN}                           N0MAD QUICK INSTALLER                              ${PURPLE}║${NC}"
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

# Check if running with sudo
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script with sudo/root privileges"
    print_status "N0MAD should be installed in user space for security"
    exit 1
fi

print_header

print_status "🚀 Welcome to N0MAD Quick Installer!"
print_status "This will download and install N0MAD without requiring pip"
echo ""

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

print_status "📥 Downloading N0MAD installer..."

# Try different download methods
if command -v curl >/dev/null 2>&1; then
    curl -sSL https://raw.githubusercontent.com/ddcodepl/n0mad/master/install.sh -o install.sh
elif command -v wget >/dev/null 2>&1; then
    wget -qO install.sh https://raw.githubusercontent.com/ddcodepl/n0mad/master/install.sh
else
    print_error "Neither curl nor wget found. Please install one of them."
    exit 1
fi

print_success "Installer downloaded successfully"

print_status "🔧 Running N0MAD installer..."
chmod +x install.sh
bash install.sh

# Cleanup
cd /
rm -rf "$TEMP_DIR"

print_success "🎉 N0MAD installation completed!"
print_status "You can now use: n0mad --help"
