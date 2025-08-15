"""
Setup script for n0mad package.
N0MAD: Notion Orchestrated Management & Autonomous Developer
This file provides additional setup functionality beyond pyproject.toml.
"""

import os
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install


class PostInstallCommand(install):
    """Custom post-installation for installation mode."""

    def run(self):
        install.run(self)
        self._post_install_setup()

    def _post_install_setup(self):
        """Perform post-installation setup tasks."""
        print("🔧 Setting up N0MAD global configuration...")

        try:
            # Import after installation to ensure package is available
            from src.utils.global_config import initialize_global_config

            # Initialize global configuration
            config = initialize_global_config()

            # Create configuration template if it doesn't exist
            home_dir = config.get_home_directory()
            config_file = home_dir / "config.env"

            if not config_file.exists():
                template_path = config.create_global_config_template(str(config_file))
                print(f"✅ Created configuration template: {template_path}")
                print("📝 Edit this file to configure your API keys and settings.")
            else:
                print(f"ℹ️  Configuration file already exists: {config_file}")

            print("🎉 N0MAD installation completed successfully!")
            print()
            print("Next steps:")
            print("  1. Run: n0mad --config-help")
            print("  2. Configure your API keys in the config file")
            print("  3. Run: n0mad --config-status")
            print("  4. Start using: n0mad --help")

        except Exception as e:
            print(f"⚠️  Post-installation setup encountered an issue: {e}")
            print("You can manually run 'n0mad --config-create' after installation.")


class PostDevelopCommand(develop):
    """Custom post-installation for development mode."""

    def run(self):
        develop.run(self)
        print("🔧 Development mode installation completed.")
        print("Run 'n0mad --config-help' to get started with configuration.")


# Use pyproject.toml for main configuration, but provide custom commands
setup(
    cmdclass={
        "install": PostInstallCommand,
        "develop": PostDevelopCommand,
    },
)
