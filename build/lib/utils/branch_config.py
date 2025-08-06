#!/usr/bin/env python3
"""
Branch Creation Configuration

Configuration management for Git branch creation functionality,
including settings validation, environment variable integration,
and configuration persistence.
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


logger = logging.getLogger(__name__)


class BranchNamingStrategy(str, Enum):
    """Branch naming strategy options."""
    TASK_ID_TITLE = "task_id_title"      # task-123-feature-name
    TITLE_ONLY = "title_only"            # feature-name
    ID_ONLY = "id_only"                  # task-123
    TIMESTAMP = "timestamp"              # task-123-1234567890


@dataclass
class BranchCreationConfig:
    """Configuration settings for branch creation functionality."""
    
    # Core settings
    enabled: bool = True
    default_base_branch: str = "master"
    naming_strategy: BranchNamingStrategy = BranchNamingStrategy.TASK_ID_TITLE
    
    # Branch naming
    branch_prefix: str = ""
    max_branch_name_length: int = 250
    sanitize_branch_names: bool = True
    
    # Behavior settings
    force_branch_creation: bool = False
    switch_to_new_branch: bool = False
    push_to_remote: bool = False
    
    # Error handling
    fail_task_on_branch_error: bool = False
    retry_on_failure: bool = True
    max_retries: int = 2
    
    # Integration settings
    integrate_with_content_processor: bool = True
    integrate_with_multi_queue_processor: bool = True
    run_before_content_processing: bool = True
    
    # Checkbox detection
    checkbox_property_names: List[str] = None
    require_explicit_checkbox: bool = True
    
    # Security settings
    allowed_base_branches: List[str] = None
    forbidden_branch_patterns: List[str] = None
    
    def __post_init__(self):
        """Initialize default values after construction."""
        if self.checkbox_property_names is None:
            self.checkbox_property_names = [
                "New Branch",
                "Create Branch",
                "Branch",
                "new_branch",
                "create_branch"
            ]
        
        if self.allowed_base_branches is None:
            self.allowed_base_branches = [
                "master",
                "main", 
                "develop",
                "dev"
            ]
        
        if self.forbidden_branch_patterns is None:
            self.forbidden_branch_patterns = [
                "master",
                "main",
                "HEAD",
                "origin/*",
                "refs/*"
            ]


class BranchConfigManager:
    """
    Manages branch creation configuration with validation,
    environment variable integration, and persistence.
    """
    
    CONFIG_FILE_NAME = "branch_config.json"
    ENV_PREFIX = "NOMAD_BRANCH_"
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.config_dir = self.project_root / ".nomad"
        self.config_file = self.config_dir / self.CONFIG_FILE_NAME
        
        self._config = BranchCreationConfig()
        self._logger = logging.getLogger(__name__)
        
        self._ensure_config_directory()
        self._load_configuration()
        
        logger.info("⚙️  BranchConfigManager initialized")
        logger.info(f"   📁 Config directory: {self.config_dir}")
        logger.info(f"   📄 Config file: {self.config_file}")
    
    def _ensure_config_directory(self) -> None:
        """Ensure configuration directory exists."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"📁 Config directory ensured: {self.config_dir}")
        except Exception as e:
            logger.error(f"❌ Failed to create config directory: {e}")
            raise
    
    def _load_configuration(self) -> None:
        """Load configuration from file and environment variables."""
        # Load from file first
        self._load_from_file()
        
        # Override with environment variables
        self._load_from_environment()
        
        # Validate configuration
        self._validate_configuration()
        
        logger.info("✅ Branch configuration loaded successfully")
    
    def _load_from_file(self) -> None:
        """Load configuration from JSON file."""
        if not self.config_file.exists():
            logger.info(f"ℹ️  Config file not found, using defaults: {self.config_file}")
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Update configuration with file data
            for key, value in config_data.items():
                if hasattr(self._config, key):
                    # Handle enum fields specially
                    if key == "naming_strategy":
                        try:
                            setattr(self._config, key, BranchNamingStrategy(value))
                        except ValueError:
                            logger.warning(f"⚠️  Invalid naming strategy: {value}, using default")
                    else:
                        setattr(self._config, key, value)
                else:
                    logger.warning(f"⚠️  Unknown config key in file: {key}")
            
            logger.info(f"📄 Configuration loaded from file: {self.config_file}")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config file: {e}")
        except Exception as e:
            logger.error(f"❌ Error loading config file: {e}")
    
    def _load_from_environment(self) -> None:
        """Load configuration from environment variables."""
        env_mappings = {
            f"{self.ENV_PREFIX}ENABLED": ("enabled", lambda x: x.lower() in ['true', '1', 'yes']),
            f"{self.ENV_PREFIX}DEFAULT_BASE_BRANCH": ("default_base_branch", str),
            f"{self.ENV_PREFIX}NAMING_STRATEGY": ("naming_strategy", lambda x: BranchNamingStrategy(x)),
            f"{self.ENV_PREFIX}BRANCH_PREFIX": ("branch_prefix", str),
            f"{self.ENV_PREFIX}MAX_BRANCH_NAME_LENGTH": ("max_branch_name_length", int),
            f"{self.ENV_PREFIX}FORCE_CREATION": ("force_branch_creation", lambda x: x.lower() in ['true', '1', 'yes']),
            f"{self.ENV_PREFIX}SWITCH_TO_BRANCH": ("switch_to_new_branch", lambda x: x.lower() in ['true', '1', 'yes']),
            f"{self.ENV_PREFIX}PUSH_TO_REMOTE": ("push_to_remote", lambda x: x.lower() in ['true', '1', 'yes']),
            f"{self.ENV_PREFIX}FAIL_ON_ERROR": ("fail_task_on_branch_error", lambda x: x.lower() in ['true', '1', 'yes']),
            f"{self.ENV_PREFIX}MAX_RETRIES": ("max_retries", int),
        }
        
        for env_var, (attr_name, converter) in env_mappings.items():
            if env_var in os.environ:
                try:
                    value = converter(os.environ[env_var])
                    setattr(self._config, attr_name, value)
                    logger.info(f"⚙️  Updated from env: {attr_name} = {value}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️  Invalid environment value for {env_var}: {e}")
    
    def _validate_configuration(self) -> None:
        """Validate the current configuration."""
        errors = []
        
        # Validate max branch name length
        if self._config.max_branch_name_length < 1 or self._config.max_branch_name_length > 255:
            errors.append("max_branch_name_length must be between 1 and 255")
        
        # Validate max retries
        if self._config.max_retries < 0 or self._config.max_retries > 10:
            errors.append("max_retries must be between 0 and 10")
        
        # Validate base branch is allowed
        if (self._config.allowed_base_branches and 
            self._config.default_base_branch not in self._config.allowed_base_branches):
            errors.append(f"default_base_branch '{self._config.default_base_branch}' not in allowed list")
        
        # Validate checkbox property names
        if not self._config.checkbox_property_names:
            errors.append("checkbox_property_names cannot be empty")
        
        if errors:
            error_msg = "Configuration validation errors: " + "; ".join(errors)
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info("✅ Configuration validation passed")
    
    def save_configuration(self) -> None:
        """Save current configuration to file."""
        try:
            config_dict = asdict(self._config)
            
            # Convert enum to string for JSON serialization
            config_dict["naming_strategy"] = self._config.naming_strategy.value
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Configuration saved to: {self.config_file}")
            
        except Exception as e:
            logger.error(f"❌ Error saving configuration: {e}")
            raise
    
    def get_config(self) -> BranchCreationConfig:
        """Get current configuration."""
        return self._config
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
        """
        for key, value in updates.items():
            if hasattr(self._config, key):
                # Handle enum fields specially
                if key == "naming_strategy":
                    if isinstance(value, str):
                        try:
                            value = BranchNamingStrategy(value)
                        except ValueError:
                            logger.warning(f"⚠️  Invalid naming strategy: {value}")
                            continue
                
                setattr(self._config, key, value)
                logger.info(f"⚙️  Updated config: {key} = {value}")
            else:
                logger.warning(f"⚠️  Unknown configuration key: {key}")
        
        # Validate after updates
        self._validate_configuration()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self._config = BranchCreationConfig()
        logger.info("🔄 Configuration reset to defaults")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration."""
        config_dict = asdict(self._config)
        config_dict["naming_strategy"] = self._config.naming_strategy.value
        
        return {
            "config": config_dict,
            "config_file": str(self.config_file),
            "file_exists": self.config_file.exists(),
            "validation_status": "valid"  # Will be "valid" if we reach here
        }
    
    def is_branch_creation_enabled(self) -> bool:
        """Check if branch creation is enabled."""
        return self._config.enabled
    
    def is_base_branch_allowed(self, branch_name: str) -> bool:
        """Check if a base branch is allowed."""
        if not self._config.allowed_base_branches:
            return True
        return branch_name in self._config.allowed_base_branches
    
    def is_branch_name_forbidden(self, branch_name: str) -> bool:
        """Check if a branch name matches forbidden patterns."""
        if not self._config.forbidden_branch_patterns:
            return False
        
        import fnmatch
        for pattern in self._config.forbidden_branch_patterns:
            if fnmatch.fnmatch(branch_name, pattern):
                return True
        return False
    
    def get_effective_checkbox_properties(self) -> List[str]:
        """Get the effective list of checkbox property names to check."""
        return self._config.checkbox_property_names.copy()
    
    def create_default_config_file(self) -> None:
        """Create a default configuration file with comments."""
        config_content = {
            "_comment": "Branch Creation Configuration for Nomad Task Processing",
            "_description": "Configure Git branch creation behavior for task processing",
            
            "enabled": True,
            "default_base_branch": "master",
            "naming_strategy": "task_id_title",
            
            "branch_prefix": "",
            "max_branch_name_length": 250,
            "sanitize_branch_names": True,
            
            "force_branch_creation": False,
            "switch_to_new_branch": False,
            "push_to_remote": False,
            
            "fail_task_on_branch_error": False,
            "retry_on_failure": True,
            "max_retries": 2,
            
            "integrate_with_content_processor": True,
            "integrate_with_multi_queue_processor": True,
            "run_before_content_processing": True,
            
            "checkbox_property_names": [
                "New Branch",
                "Create Branch", 
                "Branch"
            ],
            "require_explicit_checkbox": True,
            
            "allowed_base_branches": [
                "master",
                "main",
                "develop"
            ],
            "forbidden_branch_patterns": [
                "master",
                "main", 
                "HEAD"
            ]
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_content, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 Default configuration file created: {self.config_file}")
            
        except Exception as e:
            logger.error(f"❌ Error creating default config file: {e}")
            raise


# Global configuration manager instance (initialized when imported)
_global_config_manager: Optional[BranchConfigManager] = None


def get_branch_config_manager(project_root: str = None) -> BranchConfigManager:
    """
    Get the global branch configuration manager instance.
    
    Args:
        project_root: Project root directory (required for first call)
        
    Returns:
        BranchConfigManager instance
    """
    global _global_config_manager
    
    if _global_config_manager is None:
        if project_root is None:
            raise ValueError("project_root is required for first call to get_branch_config_manager")
        _global_config_manager = BranchConfigManager(project_root)
    
    return _global_config_manager


def get_branch_config(project_root: str = None) -> BranchCreationConfig:
    """
    Get the current branch creation configuration.
    
    Args:
        project_root: Project root directory (required for first call)
        
    Returns:
        BranchCreationConfig instance
    """
    return get_branch_config_manager(project_root).get_config()