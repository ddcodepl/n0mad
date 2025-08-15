"""
Typed configuration management with comprehensive type hints and validation.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, Protocol, TypeVar, Union, runtime_checkable

from typing_extensions import Literal, TypedDict

# Type aliases for better readability
ConfigValue = Union[str, int, bool, float, None]
ConfigDict = Dict[str, ConfigValue]
PathLike = Union[str, Path]


class LogLevel(Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class APIProvider(Enum):
    """Supported AI API providers."""

    OPENAI = "openai"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    MISTRAL = "mistral"
    COHERE = "cohere"
    XAI = "xai"


@runtime_checkable
class ConfigValidator(Protocol):
    """Protocol for configuration validators."""

    def validate(self, value: Any) -> bool:
        """Validate a configuration value."""
        ...

    def get_error_message(self, value: Any) -> str:
        """Get error message for invalid value."""
        ...


class ValidationConfig(TypedDict, total=False):
    """Configuration for validation settings."""

    enabled: bool
    checkbox_name: str
    cache_ttl_minutes: int
    strict_mode: bool
    checkbox_names: List[str]


class PollingConfig(TypedDict, total=False):
    """Configuration for polling settings."""

    enable_continuous_polling: bool
    polling_interval_minutes: int
    polling_interval_seconds: int
    min_interval_minutes: int
    max_interval_minutes: int
    is_valid: bool


class SecurityConfig(TypedDict, total=False):
    """Configuration for security settings."""

    mask_sensitive_values: bool
    validate_api_key_format: bool
    check_environment_leaks: bool
    strict_validation: bool


@dataclass(frozen=True)
class EnvironmentVariable:
    """Represents an environment variable configuration."""

    name: str
    description: str
    default: Optional[ConfigValue]
    required: bool
    validator: Optional[ConfigValidator] = None
    sensitive: bool = False

    def __post_init__(self):
        """Validate the environment variable configuration."""
        if self.required and self.default is None:
            object.__setattr__(self, "default", "")


@dataclass
class ConfigurationState:
    """Represents the current configuration state."""

    values: ConfigDict = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_valid: bool = True

    def add_error(self, error: str) -> None:
        """Add validation error."""
        self.validation_errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.warnings.append(warning)

    def get_value(self, key: str, default: Optional[ConfigValue] = None) -> ConfigValue:
        """Get configuration value with optional default."""
        return self.values.get(key, default)

    def set_value(self, key: str, value: ConfigValue) -> None:
        """Set configuration value."""
        self.values[key] = value

    def has_value(self, key: str) -> bool:
        """Check if configuration has a value for key."""
        return key in self.values and self.values[key] is not None


T = TypeVar("T")


class TypedConfigManager(Generic[T]):
    """Generic typed configuration manager."""

    def __init__(self, config_type: type[T]):
        self.config_type = config_type
        self.state = ConfigurationState()

    def get_typed_config(self) -> T:
        """Get configuration as typed object."""
        try:
            return self.config_type(**self.state.values)
        except TypeError as e:
            raise ValueError(f"Failed to create typed config: {e}") from e

    def validate_and_set(self, key: str, value: Any, validator: Optional[ConfigValidator] = None) -> bool:
        """Validate and set configuration value."""
        if validator and not validator.validate(value):
            self.state.add_error(validator.get_error_message(value))
            return False

        self.state.set_value(key, value)
        return True


# Specific validators
class StringValidator:
    """Validator for string values."""

    def __init__(self, min_length: int = 0, max_length: Optional[int] = None, pattern: Optional[str] = None):
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        if pattern:
            import re

            self.regex = re.compile(pattern)

    def validate(self, value: Any) -> bool:
        """Validate string value."""
        if not isinstance(value, str):
            return False

        if len(value) < self.min_length:
            return False

        if self.max_length and len(value) > self.max_length:
            return False

        if hasattr(self, "regex") and not self.regex.match(value):
            return False

        return True

    def get_error_message(self, value: Any) -> str:
        """Get error message for invalid value."""
        if not isinstance(value, str):
            return f"Expected string, got {type(value).__name__}"

        if len(value) < self.min_length:
            return f"String too short (minimum {self.min_length} characters)"

        if self.max_length and len(value) > self.max_length:
            return f"String too long (maximum {self.max_length} characters)"

        if hasattr(self, "regex") and not self.regex.match(value):
            return f"String does not match required pattern: {self.pattern}"

        return "Invalid string value"


class IntegerValidator:
    """Validator for integer values."""

    def __init__(self, min_value: Optional[int] = None, max_value: Optional[int] = None):
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any) -> bool:
        """Validate integer value."""
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            return False

        if self.min_value is not None and int_value < self.min_value:
            return False

        if self.max_value is not None and int_value > self.max_value:
            return False

        return True

    def get_error_message(self, value: Any) -> str:
        """Get error message for invalid value."""
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            return f"Expected integer, got {type(value).__name__}"

        if self.min_value is not None and int_value < self.min_value:
            return f"Value too small (minimum {self.min_value})"

        if self.max_value is not None and int_value > self.max_value:
            return f"Value too large (maximum {self.max_value})"

        return "Invalid integer value"


class BooleanValidator:
    """Validator for boolean values."""

    def validate(self, value: Any) -> bool:
        """Validate boolean value."""
        if isinstance(value, bool):
            return True

        if isinstance(value, str):
            return value.lower() in ("true", "false", "1", "0", "yes", "no", "on", "off")

        return False

    def get_error_message(self, value: Any) -> str:
        """Get error message for invalid value."""
        return f"Expected boolean or boolean-like string, got {type(value).__name__}: {value}"


class PathValidator:
    """Validator for file system paths."""

    def __init__(self, must_exist: bool = False, must_be_writable: bool = False):
        self.must_exist = must_exist
        self.must_be_writable = must_be_writable

    def validate(self, value: Any) -> bool:
        """Validate path value."""
        if not isinstance(value, (str, Path)):
            return False

        try:
            path = Path(value).expanduser().resolve()
        except (OSError, ValueError):
            return False

        if self.must_exist and not path.exists():
            return False

        if self.must_be_writable:
            # Check if parent directory is writable
            parent = path.parent
            if not parent.exists() or not os.access(parent, os.W_OK):
                return False

        return True

    def get_error_message(self, value: Any) -> str:
        """Get error message for invalid value."""
        if not isinstance(value, (str, Path)):
            return f"Expected path string or Path object, got {type(value).__name__}"

        try:
            path = Path(value).expanduser().resolve()
        except (OSError, ValueError):
            return f"Invalid path format: {value}"

        if self.must_exist and not path.exists():
            return f"Path does not exist: {path}"

        if self.must_be_writable:
            parent = path.parent
            if not parent.exists():
                return f"Parent directory does not exist: {parent}"
            if not os.access(parent, os.W_OK):
                return f"Parent directory is not writable: {parent}"

        return "Invalid path"


class APIKeyValidator:
    """Validator for API keys."""

    def __init__(self, provider: Optional[APIProvider] = None, min_length: int = 10):
        self.provider = provider
        self.min_length = min_length

    def validate(self, value: Any) -> bool:
        """Validate API key value."""
        if not isinstance(value, str):
            return False

        value = value.strip()
        if len(value) < self.min_length:
            return False

        # Check for placeholder text
        placeholder_texts = [
            "your_key_here",
            "api_key",
            "secret",
            "token",
            "replace_me",
            "example",
            "demo",
            "test",
        ]
        if any(placeholder.lower() in value.lower() for placeholder in placeholder_texts):
            return False

        # Provider-specific validation
        if self.provider == APIProvider.OPENAI:
            return value.startswith("sk-") and len(value) >= 40
        elif self.provider == APIProvider.ANTHROPIC:
            return value.startswith("sk-ant-") and len(value) >= 40

        return True

    def get_error_message(self, value: Any) -> str:
        """Get error message for invalid value."""
        if not isinstance(value, str):
            return f"Expected string API key, got {type(value).__name__}"

        value = value.strip()
        if len(value) < self.min_length:
            return f"API key too short (minimum {self.min_length} characters)"

        placeholder_texts = [
            "your_key_here",
            "api_key",
            "secret",
            "token",
            "replace_me",
            "example",
            "demo",
            "test",
        ]
        if any(placeholder.lower() in value.lower() for placeholder in placeholder_texts):
            return "API key appears to be a placeholder value"

        if self.provider:
            return f"Invalid {self.provider.value} API key format"

        return "Invalid API key format"


# Predefined environment variables with validators
ENVIRONMENT_VARIABLES: Dict[str, EnvironmentVariable] = {
    "NOMAD_HOME": EnvironmentVariable(
        name="NOMAD_HOME",
        description="Base directory for Nomad files",
        default=str(Path.home() / ".nomad"),
        required=False,
        validator=PathValidator(must_be_writable=True),
    ),
    "NOTION_TOKEN": EnvironmentVariable(
        name="NOTION_TOKEN",
        description="Notion API integration token",
        default=None,
        required=True,
        validator=StringValidator(min_length=32, pattern=r"^secret_.*"),
        sensitive=True,
    ),
    "NOTION_BOARD_DB": EnvironmentVariable(
        name="NOTION_BOARD_DB",
        description="Notion database ID for task management",
        default=None,
        required=True,
        validator=StringValidator(min_length=32, pattern=r"^[a-f0-9-]{32,}$"),
    ),
    "OPENAI_API_KEY": EnvironmentVariable(
        name="OPENAI_API_KEY",
        description="OpenAI API key for content processing",
        default=None,
        required=False,
        validator=APIKeyValidator(APIProvider.OPENAI),
        sensitive=True,
    ),
    "ANTHROPIC_API_KEY": EnvironmentVariable(
        name="ANTHROPIC_API_KEY",
        description="Anthropic API key for Claude integration",
        default=None,
        required=False,
        validator=APIKeyValidator(APIProvider.ANTHROPIC),
        sensitive=True,
    ),
    "NOMAD_LOG_LEVEL": EnvironmentVariable(
        name="NOMAD_LOG_LEVEL",
        description="Logging level",
        default="INFO",
        required=False,
        validator=StringValidator(pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    ),
    "NOMAD_MAX_CONCURRENT_TASKS": EnvironmentVariable(
        name="NOMAD_MAX_CONCURRENT_TASKS",
        description="Maximum number of concurrent tasks",
        default="3",
        required=False,
        validator=IntegerValidator(min_value=1, max_value=20),
    ),
}


def get_environment_variable_config(name: str) -> Optional[EnvironmentVariable]:
    """Get environment variable configuration by name."""
    return ENVIRONMENT_VARIABLES.get(name)


def get_all_environment_variables() -> Dict[str, EnvironmentVariable]:
    """Get all environment variable configurations."""
    return ENVIRONMENT_VARIABLES.copy()


def create_validation_config() -> ValidationConfig:
    """Create validation configuration from environment."""
    from .singleton_config import get_config

    config = get_config()

    return ValidationConfig(
        enabled=config.get("NOMAD_COMMIT_VALIDATION_ENABLED", "true").lower() == "true",
        checkbox_name=config.get("NOMAD_COMMIT_CHECKBOX_NAME", "Commit"),
        cache_ttl_minutes=int(config.get("NOMAD_VALIDATION_CACHE_TTL_MINUTES", "5")),
        strict_mode=config.get("NOMAD_VALIDATION_STRICT_MODE", "false").lower() == "true",
        checkbox_names=[
            config.get("NOMAD_COMMIT_CHECKBOX_NAME", "Commit"),
            "commit",
            "Ready to commit",
            "Can commit",
            "Ready to Commit",
            "Commit Ready",
            "Commit?",
        ],
    )
