"""
Environment variable security utilities for Nomad.
Handles secure loading, validation, and masking of sensitive environment variables.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EnvironmentSecurityManager:
    """Manages secure handling of environment variables."""

    # Patterns for sensitive variable names
    SENSITIVE_PATTERNS = [
        r".*KEY.*",
        r".*TOKEN.*",
        r".*SECRET.*",
        r".*PASSWORD.*",
        r".*AUTH.*",
        r".*CREDENTIAL.*",
    ]

    # Known API key prefixes for validation
    API_KEY_PREFIXES = {
        "openai": ["sk-"],
        "anthropic": ["sk-ant-"],
        # Notion tokens can have various formats, so we don't enforce a prefix
        "openrouter": ["sk-or-"],
        "mistral": ["api_key_"],
        "cohere": ["co-"],
        "xai": ["xai-"],
    }

    def __init__(self):
        self.sensitive_vars = set()
        self._compile_sensitive_patterns()

    def _compile_sensitive_patterns(self):
        """Compile regex patterns for sensitive variable detection."""
        self.sensitive_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.SENSITIVE_PATTERNS]

    def is_sensitive_variable(self, var_name: str) -> bool:
        """Check if a variable name indicates it contains sensitive data."""
        return any(pattern.match(var_name) for pattern in self.sensitive_regex)

    def mask_sensitive_value(self, value: str, show_chars: int = 4) -> str:
        """Mask a sensitive value for safe logging/display."""
        if not value or len(value) <= show_chars * 2:
            return "***"

        return f"{value[:show_chars]}{'*' * (len(value) - show_chars * 2)}{value[-show_chars:]}"

    def validate_api_key_format(self, provider: str, api_key: str) -> Tuple[bool, List[str]]:
        """
        Validate API key format for specific providers.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        if not isinstance(api_key, str):
            issues.append("API key must be a string")
            return False, issues

        api_key = api_key.strip()
        if not api_key:
            issues.append("API key cannot be empty")
            return False, issues

        # Check minimum length
        if len(api_key) < 10:
            issues.append("API key too short (minimum 10 characters)")

        # Check for obvious placeholder text
        placeholder_texts = [
            "your_key_here",
            "api_key",
            "secret",
            "token",
            "replace_me",
            "example",
            "demo",
            "test",
            "placeholder",
            "changeme",
        ]

        if any(placeholder.lower() in api_key.lower() for placeholder in placeholder_texts):
            issues.append("API key appears to be a placeholder")

        # Provider-specific validation
        provider_lower = provider.lower()
        if provider_lower in self.API_KEY_PREFIXES:
            expected_prefixes = self.API_KEY_PREFIXES[provider_lower]
            if not any(api_key.startswith(prefix) for prefix in expected_prefixes):
                issues.append(f"API key should start with one of: {', '.join(expected_prefixes)}")

        # Additional security checks
        if api_key.count(" ") > 2:
            issues.append("API key contains too many spaces")

        # Check for suspicious patterns
        if re.search(r'[<>"\']', api_key):
            issues.append("API key contains suspicious characters")

        # Check for newlines or control characters
        if any(ord(c) < 32 for c in api_key if c not in ["\t"]):
            issues.append("API key contains control characters")

        return len(issues) == 0, issues

    def validate_notion_token(self, token: str) -> bool:
        """Validate Notion token format."""
        if not isinstance(token, str):
            return False

        token = token.strip()
        if not token:
            return False

        # Notion tokens typically start with 'secret_' and are quite long
        if token.startswith("secret_") and len(token) > 40:
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
        clean_id = db_id.replace("-", "")

        # Should be 32 characters hexadecimal
        if len(clean_id) != 32:
            return False

        try:
            int(clean_id, 16)  # Validate it's hexadecimal
            return True
        except ValueError:
            return False

    def sanitize_for_logging(self, data: Any) -> Any:
        """Sanitize data structure for safe logging by masking sensitive values."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if self.is_sensitive_variable(key):
                    sanitized[key] = self.mask_sensitive_value(str(value)) if value else None
                else:
                    sanitized[key] = self.sanitize_for_logging(value)
            return sanitized
        elif isinstance(data, list):
            return [self.sanitize_for_logging(item) for item in data]
        elif isinstance(data, str) and len(data) > 20:
            # Check if this looks like an API key
            if any(data.startswith(prefix) for prefixes in self.API_KEY_PREFIXES.values() for prefix in prefixes):
                return self.mask_sensitive_value(data)

        return data

    def validate_environment_security(self, config: Dict[str, str]) -> Dict[str, Any]:
        """Validate security aspects of environment configuration."""
        results = {"secure": True, "warnings": [], "errors": [], "recommendations": []}

        # Check for sensitive variables in insecure locations
        if os.path.exists(".env"):
            env_stat = os.stat(".env")
            if oct(env_stat.st_mode)[-3:] != "600":
                results["warnings"].append(".env file permissions are not secure (should be 600)")
                results["recommendations"].append("Run: chmod 600 .env")

        # Check for potential security issues
        for var_name, value in config.items():
            if not value:
                continue

            if self.is_sensitive_variable(var_name):
                # Check if sensitive variable is set via environment vs file
                if os.getenv(var_name) == value:
                    # It's set in environment - check if it's in shell history risk
                    results["recommendations"].append(f"Consider using config file instead of shell environment for {var_name}")

                # Validate the sensitive value
                if var_name.endswith("_API_KEY") or var_name.endswith("_TOKEN"):
                    provider = var_name.replace("_API_KEY", "").replace("_TOKEN", "").lower()
                    is_valid, issues = self.validate_api_key_format(provider, value)

                    if not is_valid:
                        results["secure"] = False
                        results["errors"].extend([f"{var_name}: {issue}" for issue in issues])

        return results

    def secure_config_summary(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a secure summary of configuration suitable for logging."""
        summary = {}

        for key, value in config.items():
            if self.is_sensitive_variable(key):
                if value:
                    summary[key] = {
                        "set": True,
                        "length": len(str(value)),
                        "masked_value": self.mask_sensitive_value(str(value)),
                    }
                else:
                    summary[key] = {"set": False}
            else:
                summary[key] = value

        return summary

    def check_environment_leaks(self) -> List[str]:
        """Check for potential environment variable leaks."""
        warnings = []

        # Check common places where environment variables might leak
        potential_leak_files = [
            ".bash_history",
            ".zsh_history",
            ".history",
            "docker-compose.yml",
            "Dockerfile",
            ".github/workflows/*.yml",
            ".gitlab-ci.yml",
        ]

        for file_pattern in potential_leak_files:
            if "*" in file_pattern:
                # Handle glob patterns
                from glob import glob

                files = glob(file_pattern)
            else:
                files = [file_pattern] if os.path.exists(file_pattern) else []

            for file_path in files:
                try:
                    if os.path.exists(file_path) and os.path.getsize(file_path) < 1024 * 1024:  # Only check files < 1MB
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        # Look for potential API keys in content
                        for prefix_list in self.API_KEY_PREFIXES.values():
                            for prefix in prefix_list:
                                if prefix in content:
                                    warnings.append(f"Potential API key found in {file_path}")
                                    break
                except (OSError, UnicodeDecodeError, PermissionError):
                    # Skip files we can't read
                    continue

        return warnings


# Global instance
env_security = EnvironmentSecurityManager()


def validate_env_security(config: Dict[str, str]) -> Dict[str, Any]:
    """Validate environment security - convenience function."""
    return env_security.validate_environment_security(config)


def mask_sensitive_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive values in dictionary - convenience function."""
    return env_security.sanitize_for_logging(data)


def is_api_key_valid(provider: str, api_key: str) -> bool:
    """Check if API key is valid for provider - convenience function."""
    is_valid, _ = env_security.validate_api_key_format(provider, api_key)
    return is_valid
