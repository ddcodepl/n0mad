#!/usr/bin/env python3
"""
Model Parser and Validation Utility

Provides comprehensive parsing and validation for provider/model format strings.
Supports format: provider/model (e.g., 'openai/gpt-4', 'anthropic/claude-3-sonnet')
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for model validation errors"""

    pass


class ProviderType(str, Enum):
    """Supported AI providers"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    GOOGLE = "google"
    MISTRAL = "mistral"
    META = "meta"
    COHERE = "cohere"
    XAI = "xai"


@dataclass
class ParsedModel:
    """Container for parsed model information"""

    provider: str
    model: str
    original_string: str
    is_valid: bool = True
    validation_errors: list = None

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []


class ModelParser:
    """Enhanced model string parser with comprehensive validation"""

    # Default fallback model
    DEFAULT_MODEL = "openai/gpt-4o-mini"

    # Validation patterns
    PROVIDER_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")

    # Known provider endpoints and characteristics
    PROVIDER_CONFIG = {
        ProviderType.OPENAI: {
            "base_url": None,  # Uses default OpenAI client
            "requires_api_key": True,
            "common_models": ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
        },
        ProviderType.ANTHROPIC: {
            "base_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "common_models": [
                "claude-3-opus",
                "claude-3-sonnet",
                "claude-3-haiku",
                "claude-3-5-sonnet",
            ],
        },
        ProviderType.OPENROUTER: {
            "base_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "common_models": ["auto"],  # OpenRouter handles routing
        },
        ProviderType.GOOGLE: {
            "base_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "common_models": ["gemini-1.5-pro", "gemini-1.5-flash"],
        },
        ProviderType.MISTRAL: {
            "base_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "common_models": ["mistral-large", "mistral-medium", "mistral-small"],
        },
        ProviderType.META: {
            "base_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "common_models": ["llama-3.1-405b", "llama-3.1-70b", "llama-3.1-8b"],
        },
        ProviderType.COHERE: {
            "base_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "common_models": ["command-r-plus", "command-r", "command"],
        },
        ProviderType.XAI: {
            "base_url": "https://openrouter.ai/api/v1",
            "requires_api_key": True,
            "common_models": ["grok-beta"],
        },
    }

    @classmethod
    def parse_model_string(cls, model_string: Optional[str], strict_validation: bool = True) -> ParsedModel:
        """
        Parse and validate a model string in provider/model format.

        Args:
            model_string: String in format 'provider/model' or None for default
            strict_validation: If True, applies strict validation rules

        Returns:
            ParsedModel object with parsing results and validation status

        Raises:
            ValidationError: If strict_validation=True and validation fails
        """
        if not model_string or not model_string.strip():
            logger.info(f"Empty model string provided, using default: {cls.DEFAULT_MODEL}")
            return cls.parse_model_string(cls.DEFAULT_MODEL, strict_validation=False)

        model_string = model_string.strip()
        original_string = model_string
        errors = []

        # Basic format validation
        if "/" not in model_string:
            error_msg = f"Model string '{model_string}' must contain '/' separator (format: provider/model)"
            errors.append(error_msg)
            if strict_validation:
                raise ValidationError(error_msg)
            # Try to recover by using as model with default provider
            provider, model = "openai", model_string
        else:
            # Split on first '/' only to handle models with '/' in name
            parts = model_string.split("/", 1)
            if len(parts) != 2:
                error_msg = f"Invalid model string format: '{model_string}'"
                errors.append(error_msg)
                if strict_validation:
                    raise ValidationError(error_msg)
                return ParsedModel("", "", original_string, False, errors)

            provider, model = parts

        # Validate provider
        provider = provider.strip().lower()
        if not provider:
            error_msg = "Provider cannot be empty"
            errors.append(error_msg)
            if strict_validation:
                raise ValidationError(error_msg)
        elif not cls.PROVIDER_PATTERN.match(provider):
            error_msg = f"Invalid provider format: '{provider}'. Must be alphanumeric with optional hyphens/underscores"
            errors.append(error_msg)
            if strict_validation:
                raise ValidationError(error_msg)

        # Validate model
        model = model.strip()
        if not model:
            error_msg = "Model cannot be empty"
            errors.append(error_msg)
            if strict_validation:
                raise ValidationError(error_msg)
        elif not cls.MODEL_PATTERN.match(model):
            error_msg = f"Invalid model format: '{model}'. Must be alphanumeric with optional dots, hyphens, underscores"
            errors.append(error_msg)
            if strict_validation:
                raise ValidationError(error_msg)

        # Additional validation for known providers
        if provider in [p.value for p in ProviderType]:
            cls._validate_known_provider(provider, model, errors, strict_validation)

        is_valid = len(errors) == 0
        return ParsedModel(provider, model, original_string, is_valid, errors)

    @classmethod
    def _validate_known_provider(cls, provider: str, model: str, errors: list, strict_validation: bool) -> None:
        """Validate model against known provider configurations"""
        try:
            provider_enum = ProviderType(provider)
            config = cls.PROVIDER_CONFIG.get(provider_enum)

            if config and "common_models" in config:
                common_models = config["common_models"]
                # For openrouter and some providers, skip model validation as they support many models
                # Also be flexible about case sensitivity and minor variations
                if provider_enum not in [ProviderType.OPENROUTER]:
                    model_lower = model.lower()
                    common_models_lower = [m.lower() for m in common_models]
                    if model_lower not in common_models_lower:
                        warning_msg = f"Model '{model}' not in common models for provider '{provider}'. Common models: {common_models}"
                        logger.warning(warning_msg)
                        # Only add as error for very strict validation, and only for critical issues
                        # Allow flexibility for model variations
                        if strict_validation and not any(model_lower.startswith(cm.split("-")[0]) for cm in common_models_lower):
                            errors.append(warning_msg)

        except ValueError:
            # Provider not in enum, which is fine for extensibility
            pass

    @classmethod
    def get_provider_config(cls, provider: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific provider"""
        try:
            provider_enum = ProviderType(provider.lower())
            return cls.PROVIDER_CONFIG.get(provider_enum)
        except ValueError:
            return None

    @classmethod
    def is_openai_provider(cls, provider: str) -> bool:
        """Check if provider should use direct OpenAI client"""
        return provider.lower() == ProviderType.OPENAI.value

    @classmethod
    def requires_openrouter(cls, provider: str) -> bool:
        """Check if provider requires OpenRouter routing"""
        return provider.lower() != ProviderType.OPENAI.value

    @classmethod
    def validate_and_normalize(cls, model_string: Optional[str]) -> Tuple[str, str]:
        """
        Validate and normalize a model string, returning (provider, model) tuple.

        Args:
            model_string: Model string to validate

        Returns:
            Tuple of (provider, model)

        Raises:
            ValidationError: If validation fails
        """
        parsed = cls.parse_model_string(model_string, strict_validation=True)
        return parsed.provider, parsed.model

    @classmethod
    def get_default_model(cls) -> Tuple[str, str]:
        """Get default provider and model"""
        parsed = cls.parse_model_string(cls.DEFAULT_MODEL, strict_validation=False)
        return parsed.provider, parsed.model

    @classmethod
    def format_model_string(cls, provider: str, model: str) -> str:
        """Format provider and model into standard string format"""
        return f"{provider.strip().lower()}/{model.strip()}"

    @classmethod
    def get_supported_providers(cls) -> list:
        """Get list of supported provider names"""
        return [provider.value for provider in ProviderType]


# Convenience functions for backward compatibility and ease of use
def parse_model(model_string: Optional[str]) -> Tuple[str, str]:
    """Simple parsing function that returns (provider, model) tuple"""
    parsed = ModelParser.parse_model_string(model_string, strict_validation=False)
    return parsed.provider, parsed.model


def validate_model(model_string: str) -> bool:
    """Simple validation function that returns True/False"""
    try:
        parsed = ModelParser.parse_model_string(model_string, strict_validation=True)
        return parsed.is_valid
    except ValidationError:
        return False


def is_openai_model(model_string: str) -> bool:
    """Check if model string specifies OpenAI provider"""
    provider, _ = parse_model(model_string)
    return ModelParser.is_openai_provider(provider)


def requires_openrouter_routing(model_string: str) -> bool:
    """Check if model string requires OpenRouter routing"""
    provider, _ = parse_model(model_string)
    return ModelParser.requires_openrouter(provider)
