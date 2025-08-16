"""
N0MAD - Notion Orchestrated Management & Autonomous Developer

N0MAD is an AI-powered autonomous developer that integrates with Notion to provide
intelligent task management, automated development workflows, and seamless AI collaboration.
Built with support for Claude, OpenAI, Anthropic, and other leading AI providers.
"""

__version__ = "0.0.6"
__author__ = "N0MAD Development Team"
__license__ = "MIT"

# Package metadata
__title__ = "n0mad"
__description__ = "N0MAD: Notion Orchestrated Management & Autonomous Developer - AI-powered Notion automation with autonomous development capabilities"
__url__ = "https://github.com/ddcodepl/n0mad"

from .utils.env_security import EnvironmentSecurityManager

# Import main components for programmatic access
from .utils.global_config import GlobalConfigManager, get_global_config, initialize_global_config

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
