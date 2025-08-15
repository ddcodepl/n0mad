#!/usr/bin/env python3
"""
Unit tests for model parser and validation functionality
"""

import os
import sys

import pytest

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from model_parser import ModelParser, ParsedModel, ProviderType, ValidationError, is_openai_model, parse_model, requires_openrouter_routing, validate_model


class TestModelParser:
    """Test cases for ModelParser class"""

    def test_valid_model_formats(self):
        """Test parsing of valid model format strings"""
        test_cases = [
            ("openai/gpt-4", "openai", "gpt-4"),
            ("anthropic/claude-3-sonnet", "anthropic", "claude-3-sonnet"),
            ("google/gemini-1.5-pro", "google", "gemini-1.5-pro"),
            ("mistral/mistral-large", "mistral", "mistral-large"),
            ("OpenAI/GPT-4", "openai", "GPT-4"),  # Case normalization for provider
            ("meta/llama-3.1-405b", "meta", "llama-3.1-405b"),
            ("cohere/command-r-plus", "cohere", "command-r-plus"),
            ("xai/grok-beta", "xai", "grok-beta"),
        ]

        for model_string, expected_provider, expected_model in test_cases:
            parsed = ModelParser.parse_model_string(model_string)
            assert parsed.is_valid, f"Should be valid: {model_string}, errors: {parsed.validation_errors}"
            assert parsed.provider == expected_provider, f"Provider mismatch for {model_string}"
            assert parsed.model == expected_model, f"Model mismatch for {model_string}"
            assert parsed.original_string == model_string

    def test_invalid_model_formats(self):
        """Test parsing of invalid model format strings"""
        invalid_cases = [
            "",  # Empty string
            "   ",  # Whitespace only
            "gpt-4",  # No slash
            "openai/",  # Empty model
            "/gpt-4",  # Empty provider
            "openai//gpt-4",  # Double slash
            "open ai/gpt-4",  # Space in provider
            "openai/gpt 4",  # Space in model (invalid pattern)
            "123provider/model",  # Provider starting with number
            "provider/123",  # Model starting with number (should be valid actually)
            "provider@invalid/model",  # Invalid character in provider
        ]

        for invalid_string in invalid_cases:
            parsed = ModelParser.parse_model_string(invalid_string, strict_validation=False)
            if invalid_string.strip():  # Non-empty strings should have errors
                assert not parsed.is_valid or len(parsed.validation_errors) > 0, f"Should be invalid: '{invalid_string}'"

    def test_strict_validation_mode(self):
        """Test strict validation mode raises exceptions"""
        with pytest.raises(ValidationError):
            ModelParser.parse_model_string("invalid-format", strict_validation=True)

        with pytest.raises(ValidationError):
            ModelParser.parse_model_string("openai/", strict_validation=True)

        with pytest.raises(ValidationError):
            ModelParser.parse_model_string("/gpt-4", strict_validation=True)

    def test_default_fallback(self):
        """Test fallback to default model"""
        # None input
        parsed = ModelParser.parse_model_string(None)
        assert parsed.provider == "openai"
        assert parsed.model == "gpt-4o-mini"
        assert parsed.is_valid

        # Empty string
        parsed = ModelParser.parse_model_string("")
        assert parsed.provider == "openai"
        assert parsed.model == "gpt-4o-mini"
        assert parsed.is_valid

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Multiple slashes - should use first one
        parsed = ModelParser.parse_model_string("openai/model/with/slashes", strict_validation=False)
        assert parsed.provider == "openai"
        assert parsed.model == "model/with/slashes"

        # Whitespace handling
        parsed = ModelParser.parse_model_string("  openai  /  gpt-4  ", strict_validation=False)
        assert parsed.provider == "openai"
        assert parsed.model == "gpt-4"

        # Very long strings
        long_provider = "a" * 50
        long_model = "b" * 100
        parsed = ModelParser.parse_model_string(f"{long_provider}/{long_model}", strict_validation=False)
        assert parsed.provider == long_provider
        assert parsed.model == long_model

    def test_provider_configuration(self):
        """Test provider configuration retrieval"""
        # Known provider
        config = ModelParser.get_provider_config("openai")
        assert config is not None
        assert "requires_api_key" in config
        assert config["requires_api_key"] is True

        # Unknown provider
        config = ModelParser.get_provider_config("unknown_provider")
        assert config is None

    def test_provider_routing_logic(self):
        """Test provider routing logic"""
        # OpenAI should use direct client
        assert ModelParser.is_openai_provider("openai") is True
        assert ModelParser.is_openai_provider("OpenAI") is True
        assert ModelParser.requires_openrouter("openai") is False

        # Other providers should use OpenRouter
        for provider in ["anthropic", "google", "mistral", "meta"]:
            assert ModelParser.is_openai_provider(provider) is False
            assert ModelParser.requires_openrouter(provider) is True

    def test_validation_and_normalization(self):
        """Test validation and normalization method"""
        provider, model = ModelParser.validate_and_normalize("OpenAI/GPT-4")
        assert provider == "openai"  # Normalized to lowercase
        assert model == "GPT-4"  # Model case preserved

        with pytest.raises(ValidationError):
            ModelParser.validate_and_normalize("invalid-format")

    def test_format_model_string(self):
        """Test model string formatting"""
        formatted = ModelParser.format_model_string("  OpenAI  ", "  GPT-4  ")
        assert formatted == "openai/GPT-4"

    def test_supported_providers(self):
        """Test supported providers list"""
        providers = ModelParser.get_supported_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "google" in providers
        assert len(providers) >= 8  # We defined 8 providers


class TestConvenienceFunctions:
    """Test convenience functions for backward compatibility"""

    def test_parse_model_function(self):
        """Test simple parse_model function"""
        provider, model = parse_model("openai/gpt-4")
        assert provider == "openai"
        assert model == "gpt-4"

        # Test with None/empty
        provider, model = parse_model(None)
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_validate_model_function(self):
        """Test simple validate_model function"""
        assert validate_model("openai/gpt-4") is True
        assert validate_model("invalid-format") is False
        assert validate_model("openai/") is False

    def test_is_openai_model_function(self):
        """Test is_openai_model convenience function"""
        assert is_openai_model("openai/gpt-4") is True
        assert is_openai_model("anthropic/claude-3") is False

    def test_requires_openrouter_routing_function(self):
        """Test requires_openrouter_routing convenience function"""
        assert requires_openrouter_routing("openai/gpt-4") is False
        assert requires_openrouter_routing("anthropic/claude-3") is True
        assert requires_openrouter_routing("google/gemini") is True


class TestParsedModel:
    """Test ParsedModel dataclass"""

    def test_parsed_model_creation(self):
        """Test ParsedModel object creation"""
        parsed = ParsedModel("openai", "gpt-4", "openai/gpt-4")
        assert parsed.provider == "openai"
        assert parsed.model == "gpt-4"
        assert parsed.original_string == "openai/gpt-4"
        assert parsed.is_valid is True
        assert parsed.validation_errors == []

    def test_parsed_model_with_errors(self):
        """Test ParsedModel with validation errors"""
        errors = ["Error 1", "Error 2"]
        parsed = ParsedModel("", "", "invalid", False, errors)
        assert parsed.is_valid is False
        assert len(parsed.validation_errors) == 2


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
