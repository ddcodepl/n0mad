#!/usr/bin/env python3
"""
Simple unit tests for model parser functionality (no pytest required)
"""

import os
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from model_parser import ModelParser, ParsedModel, ProviderType, ValidationError, is_openai_model, parse_model, requires_openrouter_routing, validate_model


def test_valid_model_formats():
    """Test parsing of valid model format strings"""
    print("Testing valid model formats...")
    test_cases = [
        ("openai/gpt-4", "openai", "gpt-4"),
        ("anthropic/claude-3-sonnet", "anthropic", "claude-3-sonnet"),
        ("google/gemini-1.5-pro", "google", "gemini-1.5-pro"),
        ("OpenAI/GPT-4", "openai", "GPT-4"),  # Case normalization
    ]

    for model_string, expected_provider, expected_model in test_cases:
        parsed = ModelParser.parse_model_string(model_string)
        assert parsed.is_valid, f"Should be valid: {model_string}, errors: {parsed.validation_errors}"
        assert parsed.provider == expected_provider, f"Provider mismatch for {model_string}"
        assert parsed.model == expected_model, f"Model mismatch for {model_string}"
        print(f"✓ {model_string} -> {parsed.provider}/{parsed.model}")


def test_invalid_model_formats():
    """Test parsing of invalid model format strings"""
    print("\nTesting invalid model formats...")
    invalid_cases = [
        "gpt-4",  # No slash
        "openai/",  # Empty model
        "/gpt-4",  # Empty provider
    ]

    for invalid_string in invalid_cases:
        parsed = ModelParser.parse_model_string(invalid_string, strict_validation=False)
        assert not parsed.is_valid or len(parsed.validation_errors) > 0, f"Should be invalid: '{invalid_string}'"
        print(f"✓ '{invalid_string}' correctly identified as invalid: {parsed.validation_errors}")


def test_default_fallback():
    """Test fallback to default model"""
    print("\nTesting default fallback...")

    # None input
    parsed = ModelParser.parse_model_string(None)
    assert parsed.provider == "openai"
    assert parsed.model == "gpt-4o-mini"
    assert parsed.is_valid
    print(f"✓ None -> {parsed.provider}/{parsed.model}")

    # Empty string
    parsed = ModelParser.parse_model_string("")
    assert parsed.provider == "openai"
    assert parsed.model == "gpt-4o-mini"
    assert parsed.is_valid
    print(f"✓ Empty string -> {parsed.provider}/{parsed.model}")


def test_convenience_functions():
    """Test convenience functions"""
    print("\nTesting convenience functions...")

    # parse_model
    provider, model = parse_model("openai/gpt-4")
    assert provider == "openai" and model == "gpt-4"
    print(f"✓ parse_model('openai/gpt-4') -> {provider}, {model}")

    # validate_model
    assert validate_model("openai/gpt-4") is True
    assert validate_model("invalid-format") is False
    print("✓ validate_model works correctly")

    # is_openai_model
    assert is_openai_model("openai/gpt-4") is True
    assert is_openai_model("anthropic/claude-3") is False
    print("✓ is_openai_model works correctly")

    # requires_openrouter_routing
    assert requires_openrouter_routing("openai/gpt-4") is False
    assert requires_openrouter_routing("anthropic/claude-3") is True
    print("✓ requires_openrouter_routing works correctly")


def test_strict_validation():
    """Test strict validation mode"""
    print("\nTesting strict validation...")

    try:
        ModelParser.parse_model_string("invalid-format", strict_validation=True)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        print("✓ Strict validation correctly raises ValidationError")


def test_provider_configuration():
    """Test provider configuration"""
    print("\nTesting provider configuration...")

    config = ModelParser.get_provider_config("openai")
    assert config is not None
    assert "requires_api_key" in config
    print(f"✓ OpenAI config: {config}")

    config = ModelParser.get_provider_config("unknown_provider")
    assert config is None
    print("✓ Unknown provider returns None")


def run_all_tests():
    """Run all tests"""
    print("🧪 Running Model Parser Tests")
    print("=" * 50)

    try:
        test_valid_model_formats()
        test_invalid_model_formats()
        test_default_fallback()
        test_convenience_functions()
        test_strict_validation()
        test_provider_configuration()

        print("\n" + "=" * 50)
        print("🎉 All tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
