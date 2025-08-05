"""
Nomad - Notion task refinement and automation tool with AI integration.

A global command-line tool for automating Notion task processing with support for
OpenAI, Anthropic, and OpenRouter AI providers.
"""

__version__ = "0.2.0"
__author__ = "Nomad Development Team"
__license__ = "MIT"

# Package metadata
__title__ = "nomad-notion-automation"
__description__ = "Global Notion task refinement and automation tool with AI integration"
__url__ = "https://github.com/nomad-notion-automation/nomad"

# Import main components for programmatic access
from utils.global_config import GlobalConfigManager, get_global_config, initialize_global_config
from utils.env_security import EnvironmentSecurityManager

# Define public API
__all__ = [
    "__version__",
    "__author__", 
    "__license__",
    "GlobalConfigManager",
    "get_global_config",
    "initialize_global_config",
    "EnvironmentSecurityManager",
]