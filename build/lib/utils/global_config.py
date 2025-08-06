"""
Global configuration management for Nomad package.
Handles environment variables, paths, and global installation settings.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import logging

from .env_security import EnvironmentSecurityManager, mask_sensitive_dict

logger = logging.getLogger(__name__)

class GlobalConfigManager:
    """Manages global configuration for globally installed Nomad package."""
    
    # Environment variable definitions
    ENV_VARS = {
        'NOMAD_HOME': {
            'description': 'Base directory for Nomad files',
            'default': lambda: str(Path.home() / '.nomad'),
            'required': False
        },
        'NOMAD_TASKS_DIR': {
            'description': 'Directory for task files',
            'default': lambda: str(Path.home() / '.nomad' / 'tasks'),
            'required': False
        },
        'TASKS_DIR': {
            'description': 'Local project directory for task files',
            'default': './tasks',
            'required': True
        },
        'NOTION_TOKEN': {
            'description': 'Notion API integration token',
            'default': None,
            'required': True
        },
        'NOTION_BOARD_DB': {
            'description': 'Notion database ID for task management',
            'default': None,
            'required': True
        },
        'OPENAI_API_KEY': {
            'description': 'OpenAI API key for content processing',
            'default': None,
            'required': False
        },
        'OPENROUTER_API_KEY': {
            'description': 'OpenRouter API key as OpenAI alternative',
            'default': None,
            'required': False
        },
        'ANTHROPIC_API_KEY': {
            'description': 'Anthropic API key for Claude integration',
            'default': None,
            'required': False
        },
        'NOMAD_CONFIG_FILE': {
            'description': 'Path to additional configuration file',
            'default': lambda: str(Path.home() / '.nomad' / 'config.env'),
            'required': False
        },
        'NOMAD_LOG_LEVEL': {
            'description': 'Logging level (DEBUG, INFO, WARNING, ERROR)',
            'default': 'INFO',
            'required': False
        },
        'NOMAD_MAX_CONCURRENT_TASKS': {
            'description': 'Maximum number of concurrent tasks to process',
            'default': '3',
            'required': False
        },
        'NOMAD_COMMIT_VALIDATION_ENABLED': {
            'description': 'Enable checkbox validation for task status transitions',
            'default': 'true',
            'required': False
        },
        'NOMAD_COMMIT_CHECKBOX_NAME': {
            'description': 'Name of the commit checkbox property in Notion',
            'default': 'Commit',
            'required': False
        },
        'NOMAD_VALIDATION_CACHE_TTL_MINUTES': {
            'description': 'Cache time-to-live for checkbox validations in minutes',
            'default': '5',
            'required': False
        },
        'NOMAD_VALIDATION_STRICT_MODE': {
            'description': 'Fail transitions if checkbox not found (vs. warn and allow)',
            'default': 'false',
            'required': False
        },
        'TASKMASTER_DIR': {
            'description': 'Directory containing the taskmaster executable (defaults to ./taskmaster)',
            'default': './taskmaster',
            'required': False
        }
    }
    
    def __init__(self, working_dir: Optional[str] = None, strict_validation: bool = True):
        """
        Initialize global configuration manager.
        
        Args:
            working_dir: Optional working directory to use instead of cwd
            strict_validation: Whether to perform strict validation (raise errors)
        """
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.config = {}
        self.security_manager = EnvironmentSecurityManager()
        self.strict_validation = strict_validation
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from multiple sources in order of precedence."""
        logger.debug("Loading global configuration...")
        
        # 1. Load from local .env files (in working directory)
        self._load_local_env_files()
        
        # 2. Load from global config file
        self._load_global_config_file()
        
        # 3. Load from environment variables (highest precedence)
        self._load_environment_variables()
        
        # 4. Apply defaults for missing values
        self._apply_defaults()
        
        # 5. Validate configuration
        self._validate_configuration()
    
    def _load_local_env_files(self):
        """Load environment files from working directory."""
        local_env_files = [
            self.working_dir / '.env',
            self.working_dir / '.env.local'
        ]
        
        for env_file in local_env_files:
            if env_file.exists():
                logger.debug(f"Loading local environment from: {env_file}")
                load_dotenv(env_file, override=False)
    
    def _load_global_config_file(self):
        """Load from global configuration file if specified."""
        config_file_path = os.getenv('NOMAD_CONFIG_FILE')
        if config_file_path:
            config_file = Path(config_file_path)
            if config_file.exists():
                logger.debug(f"Loading global config from: {config_file}")
                load_dotenv(config_file, override=False)
            else:
                logger.warning(f"Global config file specified but not found: {config_file}")
    
    def _load_environment_variables(self):
        """Load values from environment variables."""
        for var_name, var_config in self.ENV_VARS.items():
            value = os.getenv(var_name)
            if value is not None:
                self.config[var_name] = value
                logger.debug(f"Loaded {var_name} from environment")
    
    def _apply_defaults(self):
        """Apply default values for missing configuration."""
        for var_name, var_config in self.ENV_VARS.items():
            if var_name not in self.config:
                default = var_config.get('default')
                if callable(default):
                    self.config[var_name] = default()
                elif default is not None:
                    self.config[var_name] = default
                else:
                    self.config[var_name] = None
    
    def _validate_configuration(self):
        """Validate required configuration values with security checks."""
        missing_required = []
        
        # Check for required fields
        for var_name, var_config in self.ENV_VARS.items():
            if var_config.get('required', False):
                value = self.config.get(var_name)
                if not value or (isinstance(value, str) and not value.strip()):
                    missing_required.append(var_name)
        
        if missing_required:
            error_msg = (
                f"Required environment variables not set: {', '.join(missing_required)}\n"
                f"Please set these variables or add them to your .env file or global config."
            )
            if self.strict_validation:
                raise ValueError(error_msg)
            else:
                logger.warning(error_msg)
        
        # Perform security validation
        security_results = self.security_manager.validate_environment_security(self.config)
        
        if not security_results['secure']:
            if self.strict_validation:
                logger.error("Security validation failed:")
                for error in security_results['errors']:
                    logger.error(f"  - {error}")
                raise ValueError("Environment configuration failed security validation")
            else:
                logger.warning("Security validation issues found:")
                for error in security_results['errors']:
                    logger.warning(f"  - {error}")
        
        # Log security warnings
        for warning in security_results['warnings']:
            logger.warning(f"Security warning: {warning}")
        
        # Log security recommendations
        for recommendation in security_results['recommendations']:
            logger.info(f"Security recommendation: {recommendation}")
        
        # Validate API keys are available
        api_key_fields = ['OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY']
        valid_api_keys = []
        
        for api_key_field in api_key_fields:
            api_key = self.config.get(api_key_field)
            if api_key:
                provider = api_key_field.replace('_API_KEY', '').lower()
                is_valid, issues = self.security_manager.validate_api_key_format(provider, api_key)
                if is_valid:
                    valid_api_keys.append(provider)
                else:
                    logger.warning(f"Invalid {provider} API key: {'; '.join(issues)}")
        
        if not valid_api_keys:
            logger.warning(
                "No valid AI API keys configured. At least one of OPENAI_API_KEY, "
                "OPENROUTER_API_KEY, or ANTHROPIC_API_KEY should be set with a valid format."
            )
        else:
            logger.info(f"Valid API keys found for providers: {', '.join(valid_api_keys)}")
        
        # Check for potential environment leaks
        leak_warnings = self.security_manager.check_environment_leaks()
        for warning in leak_warnings:
            logger.warning(f"Potential security leak: {warning}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return self.config.get(key, default)
    
    def get_required(self, key: str) -> Any:
        """Get required configuration value, raise error if missing."""
        value = self.config.get(key)
        if value is None:
            raise ValueError(f"Required configuration key '{key}' is not set")
        return value
    
    def ensure_directories(self):
        """Ensure required directories exist."""
        directories_to_create = [
            self.get('NOMAD_HOME'),
            self.get('NOMAD_TASKS_DIR'),
        ]
        
        for dir_path in directories_to_create:
            if dir_path:
                path = Path(dir_path)
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {path}")
    
    def get_tasks_directory(self) -> Path:
        """Get the tasks directory path."""
        tasks_dir = self.get('NOMAD_TASKS_DIR')
        if not tasks_dir:
            tasks_dir = str(Path.home() / '.nomad' / 'tasks')
        return Path(tasks_dir)
    
    def get_home_directory(self) -> Path:
        """Get the Nomad home directory path."""
        home_dir = self.get('NOMAD_HOME')
        if not home_dir:
            home_dir = str(Path.home() / '.nomad')
        return Path(home_dir)
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration with secure value masking."""
        summary = {}
        for var_name, var_config in self.ENV_VARS.items():
            value = self.config.get(var_name)
            
            # Use security manager to determine if value should be masked
            if self.security_manager.is_sensitive_variable(var_name) and value:
                display_value = self.security_manager.mask_sensitive_value(str(value))
            else:
                display_value = value
            
            summary[var_name] = {
                'value': display_value,
                'set': value is not None,
                'required': var_config.get('required', False),
                'description': var_config.get('description', ''),
                'is_sensitive': self.security_manager.is_sensitive_variable(var_name)
            }
        return summary
    
    def validate_working_environment(self) -> List[str]:
        """Validate the working environment and return any issues."""
        issues = []
        
        # Check Python version
        if sys.version_info < (3, 8):
            issues.append(f"Python 3.8+ required, found {sys.version}")
        
        # Check required directories are writable
        try:
            self.ensure_directories()
        except PermissionError as e:
            issues.append(f"Cannot create directories: {e}")
        
        # Check API connectivity (if configured)
        # This would be implemented in a separate validator
        
        return issues
    
    def create_global_config_template(self, path: Optional[str] = None) -> Path:
        """Create a template configuration file."""
        if path is None:
            path = self.get('NOMAD_CONFIG_FILE')
        
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        template_content = []
        template_content.append("# Nomad Global Configuration Template")
        template_content.append("# Copy this file and customize for your environment")
        template_content.append("")
        
        for var_name, var_config in self.ENV_VARS.items():
            template_content.append(f"# {var_config.get('description', '')}")
            required_text = " (REQUIRED)" if var_config.get('required') else ""
            template_content.append(f"# {var_name}{required_text}")
            
            default = var_config.get('default')
            if callable(default):
                default_value = default()
            else:
                default_value = default
            
            if default_value:
                template_content.append(f"{var_name}={default_value}")
            else:
                template_content.append(f"# {var_name}=")
            template_content.append("")
        
        config_path.write_text('\n'.join(template_content))
        logger.info(f"Created configuration template: {config_path}")
        return config_path
    
    def validate_api_key_format(self, api_key: str) -> bool:
        """Validate API key format with enhanced security checks."""
        if not isinstance(api_key, str):
            return False
        
        api_key = api_key.strip()
        if not api_key:
            return False
        
        # Basic format validation - should be at least 10 characters
        if len(api_key) < 10:
            return False
        
        # Should not contain obvious placeholder text
        placeholder_texts = ['your_key_here', 'api_key', 'secret', 'token', 'replace_me', 'example', 'demo']
        if any(placeholder.lower() in api_key.lower() for placeholder in placeholder_texts):
            return False
        
        # Additional security checks
        if api_key.count(' ') > 2:  # Too many spaces might indicate copy-paste error
            return False
        
        # Check for common patterns
        if api_key.startswith('sk-') and len(api_key) < 40:  # OpenAI keys are longer
            return False
        
        return True
    
    def validate_notion_token(self, token: str) -> bool:
        """Validate Notion token format."""
        if not isinstance(token, str):
            return False
        
        token = token.strip()
        if not token:
            return False
        
        # Notion tokens typically start with 'secret_' and are quite long
        if token.startswith('secret_') and len(token) > 40:
            return True
        
        # Also accept other formats but with minimum length
        return len(token) >= 32
    
    def validate_notion_database_id(self, db_id: str) -> bool:
        """Validate Notion database ID format."""
        if not isinstance(db_id, str):
            return False
        
        db_id = db_id.strip()
        if not db_id:
            return False
        
        # Remove hyphens for validation
        clean_id = db_id.replace('-', '')
        
        # Should be 32 characters hexadecimal
        if len(clean_id) != 32:
            return False
        
        try:
            int(clean_id, 16)  # Validate it's hexadecimal
            return True
        except ValueError:
            return False
    
    def validate_directory_path(self, path: str) -> bool:
        """Validate directory path format and accessibility."""
        if not isinstance(path, str):
            return False
        
        path = path.strip()
        if not path:
            return False
        
        try:
            path_obj = Path(path).expanduser().resolve()
            # Check if parent directory exists and is writable
            parent = path_obj.parent
            return parent.exists() and os.access(parent, os.W_OK)
        except (OSError, ValueError):
            return False
    
    def validate_log_level(self, level: str) -> bool:
        """Validate logging level."""
        if not isinstance(level, str):
            return False
        
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        return level.upper() in valid_levels
    
    def validate_max_concurrent_tasks(self, value: str) -> bool:
        """Validate max concurrent tasks setting."""
        if not isinstance(value, str):
            return False
        
        try:
            num = int(value)
            return 1 <= num <= 20  # Reasonable range
        except ValueError:
            return False
    
    def enhanced_validation(self) -> Dict[str, Any]:
        """Perform enhanced validation with detailed results."""
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'field_results': {}
        }
        
        # Validate each field with specific validators
        validators = {
            'NOTION_TOKEN': self.validate_notion_token,
            'NOTION_BOARD_DB': self.validate_notion_database_id,
            'NOMAD_HOME': self.validate_directory_path,
            'NOMAD_TASKS_DIR': self.validate_directory_path,
            'NOMAD_LOG_LEVEL': self.validate_log_level,
            'NOMAD_MAX_CONCURRENT_TASKS': self.validate_max_concurrent_tasks
        }
        
        # Validate API keys
        api_key_fields = ['OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY']
        
        for field_name, value in self.config.items():
            if value is None:
                continue
                
            field_valid = True
            field_errors = []
            field_warnings = []
            
            # Use specific validator if available
            if field_name in validators:
                if not validators[field_name](value):
                    field_valid = False
                    field_errors.append(f"Invalid format for {field_name}")
            
            # Validate API keys
            elif field_name in api_key_fields:
                if not self.validate_api_key_format(value):
                    field_valid = False
                    field_errors.append(f"Invalid API key format for {field_name}")
            
            results['field_results'][field_name] = {
                'valid': field_valid,
                'errors': field_errors,
                'warnings': field_warnings
            }
            
            if not field_valid:
                results['valid'] = False
                results['errors'].extend(field_errors)
            
            results['warnings'].extend(field_warnings)
        
        # Check for required API keys
        has_api_key = any(
            self.config.get(key) and self.validate_api_key_format(self.config.get(key))
            for key in api_key_fields
        )
        
        if not has_api_key:
            results['warnings'].append(
                "No valid AI API keys found. At least one of OPENAI_API_KEY, "
                "OPENROUTER_API_KEY, or ANTHROPIC_API_KEY is recommended."
            )
        
        return results
    
    def get_available_providers(self) -> List[str]:
        """Get list of providers with valid API keys."""
        api_key_fields = ['OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY']
        available_providers = []
        
        for api_key_field in api_key_fields:
            api_key = self.config.get(api_key_field)
            if api_key:
                provider = api_key_field.replace('_API_KEY', '').lower()
                is_valid, _ = self.security_manager.validate_api_key_format(provider, api_key)
                if is_valid:
                    available_providers.append(provider)
        
        return available_providers
    
    def get_validation_config(self) -> Dict[str, Any]:
        """
        Get validation service configuration.
        
        Returns:
            Dictionary with validation configuration
        """
        def str_to_bool(value: str) -> bool:
            """Convert string to boolean."""
            if isinstance(value, bool):
                return value
            return str(value).lower() in ('true', '1', 'yes', 'on', 'enabled')
        
        def str_to_int(value: str, default: int) -> int:
            """Convert string to integer with fallback."""
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        return {
            'enabled': str_to_bool(self.get('NOMAD_COMMIT_VALIDATION_ENABLED', 'true')),
            'checkbox_name': self.get('NOMAD_COMMIT_CHECKBOX_NAME', 'Commit'),
            'cache_ttl_minutes': str_to_int(self.get('NOMAD_VALIDATION_CACHE_TTL_MINUTES', '5'), 5),
            'strict_mode': str_to_bool(self.get('NOMAD_VALIDATION_STRICT_MODE', 'false')),
            'checkbox_names': [
                self.get('NOMAD_COMMIT_CHECKBOX_NAME', 'Commit'),
                "commit", "Ready to commit", "Can commit", 
                "Ready to Commit", "Commit Ready", "Commit?"
            ]
        }

# Global instance for easy access
global_config = None

def get_global_config(working_dir: Optional[str] = None, strict_validation: bool = True) -> GlobalConfigManager:
    """Get or create global configuration instance."""
    global global_config
    if global_config is None or working_dir is not None:
        global_config = GlobalConfigManager(working_dir, strict_validation)
    return global_config

def initialize_global_config(working_dir: Optional[str] = None, strict_validation: bool = True):
    """Initialize global configuration and ensure directories exist."""
    config = get_global_config(working_dir, strict_validation)
    config.ensure_directories()
    return config