"""
Setup script for nomad-notion-automation package.
This file provides additional setup functionality beyond pyproject.toml.
"""

from setuptools import setup
from setuptools.command.install import install
from setuptools.command.develop import develop
import os
import sys
from pathlib import Path


class PostInstallCommand(install):
    """Custom post-installation for installation mode."""
    
    def run(self):
        install.run(self)
        self._post_install_setup()
    
    def _post_install_setup(self):
        """Perform post-installation setup tasks."""
        print("🔧 Setting up Nomad global configuration...")
        
        try:
            # Import after installation to ensure package is available
            from utils.global_config import initialize_global_config
            
            # Initialize global configuration
            config = initialize_global_config()
            
            # Create configuration template if it doesn't exist
            home_dir = config.get_home_directory()
            config_file = home_dir / 'config.env'
            
            if not config_file.exists():
                template_path = config.create_global_config_template(str(config_file))
                print(f"✅ Created configuration template: {template_path}")
                print("📝 Edit this file to configure your API keys and settings.")
            else:
                print(f"ℹ️  Configuration file already exists: {config_file}")
            
            print("🎉 Nomad installation completed successfully!")
            print()
            print("Next steps:")
            print("  1. Run: nomad --config-help")
            print("  2. Configure your API keys in the config file")
            print("  3. Run: nomad --config-status")
            print("  4. Start using: nomad --help")
            
        except Exception as e:
            print(f"⚠️  Post-installation setup encountered an issue: {e}")
            print("You can manually run 'nomad --config-create' after installation.")


class PostDevelopCommand(develop):
    """Custom post-installation for development mode."""
    
    def run(self):
        develop.run(self)
        print("🔧 Development mode installation completed.")
        print("Run 'nomad --config-help' to get started with configuration.")


# Use pyproject.toml for main configuration, but provide custom commands
setup(
    cmdclass={
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
    },
)