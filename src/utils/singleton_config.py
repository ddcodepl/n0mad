"""
Singleton configuration manager for consistent global configuration access.
"""

import threading
from typing import Any, Dict, Optional

from .global_config import GlobalConfigManager


class SingletonConfigManager:
    """Thread-safe singleton configuration manager."""

    _instance: Optional[GlobalConfigManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> GlobalConfigManager:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = GlobalConfigManager(strict_validation=False)
        return cls._instance

    @classmethod
    def initialize(cls, working_dir: Optional[str] = None, strict_validation: bool = True) -> GlobalConfigManager:
        """Initialize singleton with specific parameters."""
        with cls._lock:
            cls._instance = GlobalConfigManager(working_dir, strict_validation)
        return cls._instance

    @classmethod
    def get_instance(cls) -> Optional[GlobalConfigManager]:
        """Get existing instance without creating new one."""
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (useful for testing)."""
        with cls._lock:
            cls._instance = None


def get_config() -> GlobalConfigManager:
    """Get singleton configuration instance."""
    return SingletonConfigManager()


def initialize_config(working_dir: Optional[str] = None, strict_validation: bool = True) -> GlobalConfigManager:
    """Initialize configuration with specific parameters."""
    return SingletonConfigManager.initialize(working_dir, strict_validation)
