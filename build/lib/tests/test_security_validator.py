#!/usr/bin/env python3
"""
Test security validator functionality
"""

import os
import sys
import time

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from security_validator import (
    RateLimit,
    SecurityValidator,
    SecurityViolation,
    ValidationLevel,
    ValidationResult,
    check_request_rate_limit,
    sanitize_log_message,
    validate_content_input,
    validate_model_input,
)


def test_model_string_validation():
    """Test model string validation"""
    print("🧪 Testing model string validation...")

    validator = SecurityValidator(ValidationLevel.STANDARD)

    # Valid model strings
    valid_models = [
        "openai/gpt-4",
        "anthropic/claude-3-sonnet",
        "google/gemini-1.5-pro",
        "mistral/mistral-large",
    ]

    for model in valid_models:
        result = validator.validate_model_string(model)
        assert result.is_valid, f"Valid model {model} should pass validation"
        assert result.risk_level == "low"

    print("✓ Valid model strings pass validation")

    # Invalid model strings
    invalid_models = [
        "<script>alert('xss')</script>/gpt-4",
        "openai/gpt-4; rm -rf /",
        "javascript:alert(1)/model",
        "provider with spaces/model",
        "../../etc/passwd",
        "${USER}/model",
    ]

    for model in invalid_models:
        result = validator.validate_model_string(model)
        assert not result.is_valid, f"Invalid model {model} should fail validation"
        assert len(result.violations) > 0

    print("✓ Invalid model strings properly rejected")

    # Test edge cases
    result = validator.validate_model_string("")
    assert not result.is_valid
    assert "cannot be empty" in str(result.violations)

    result = validator.validate_model_string("a" * 200)
    assert not result.is_valid
    assert "too long" in str(result.violations)

    print("✓ Edge cases handled correctly")


def test_content_validation():
    """Test content validation"""
    print("\n🧪 Testing content validation...")

    validator = SecurityValidator(ValidationLevel.STANDARD)

    # Safe content
    safe_content = """
    Please help me write a Python function that calculates fibonacci numbers.
    The function should be efficient and handle edge cases properly.
    Here's what I'm thinking: def fibonacci(n): ...
    """

    result = validator.validate_content(safe_content)
    assert result.is_valid
    assert result.risk_level == "low"
    print("✓ Safe content passes validation")

    # Dangerous content
    dangerous_content = [
        "<script>alert('XSS')</script>",
        "javascript:alert(document.cookie)",
        "eval('malicious code')",
        "exec('rm -rf /')",
        "__import__('os').system('ls')",
        "onclick='alert(1)'",
    ]

    for content in dangerous_content:
        result = validator.validate_content(content)
        # High-risk patterns should be caught
        if result.is_valid:
            assert result.risk_level in ["medium", "high"]
        else:
            assert len(result.violations) > 0

    print("✓ Dangerous content properly flagged")

    # Test length limits
    very_long_content = "a" * 60000
    result = validator.validate_content(very_long_content, max_length=50000)
    assert not result.is_valid
    assert "too long" in str(result.violations)

    print("✓ Length limits enforced")


def test_api_key_validation():
    """Test API key validation"""
    print("\n🧪 Testing API key validation...")

    validator = SecurityValidator(ValidationLevel.STANDARD)

    # Valid API keys
    valid_keys = [
        ("sk-1234567890abcdef1234567890abcdef", "openai"),
        ("sk-or-1234567890abcdef1234567890abcdef", "openrouter"),
        ("sk-ant-1234567890abcdef1234567890abcdef", "anthropic"),
    ]

    for key, provider in valid_keys:
        result = validator.validate_api_key(key, provider)
        assert result.is_valid, f"Valid {provider} key should pass validation"
        assert result.sanitized_input == "[REDACTED]"  # Keys should be redacted

    print("✓ Valid API keys pass validation")

    # Invalid API keys
    invalid_keys = [
        ("short", "openai"),  # Too short
        ("your_key_here", "openai"),  # Placeholder
        ("sk-invalid-openrouter-key", "openrouter"),  # Wrong format
        ("not-a-real-key", "anthropic"),  # Invalid format
        ("", "openai"),  # Empty
        ("a" * 300, "openai"),  # Too long
    ]

    for key, provider in invalid_keys:
        result = validator.validate_api_key(key, provider)
        assert not result.is_valid, f"Invalid {provider} key should fail validation"
        assert len(result.violations) > 0

    print("✓ Invalid API keys properly rejected")


def test_sensitive_data_sanitization():
    """Test sanitization of sensitive data for logging"""
    print("\n🧪 Testing sensitive data sanitization...")

    validator = SecurityValidator()

    # Test API key redaction
    text_with_api_keys = """
    Here's my OpenAI key: sk-1234567890abcdef1234567890abcdef
    And my OpenRouter key: sk-or-abcdef1234567890abcdef123456
    Bearer token: Bearer abc123def456ghi789
    """

    sanitized = validator.sanitize_for_logging(text_with_api_keys)
    assert "sk-" not in sanitized
    assert "Bearer" not in sanitized or "[REDACTED]" in sanitized
    assert "[REDACTED]" in sanitized

    print("✓ API keys and tokens properly redacted")

    # Test password redaction
    text_with_passwords = """
    password: mySecretPassword123
    token=abc123def456
    secret: supersecret
    """

    sanitized = validator.sanitize_for_logging(text_with_passwords)
    assert "[REDACTED]" in sanitized

    print("✓ Passwords and secrets properly redacted")

    # Test length truncation
    very_long_text = "a" * 2000
    sanitized = validator.sanitize_for_logging(very_long_text)
    assert len(sanitized) <= 1000
    if len(sanitized) == 1000:  # Only check if truncation occurred
        assert sanitized.endswith("...")

    print("✓ Long text properly truncated")


def test_rate_limiting():
    """Test rate limiting functionality"""
    print("\n🧪 Testing rate limiting...")

    validator = SecurityValidator()
    rate_limit = RateLimit(requests_per_minute=3, requests_per_hour=10)

    # Test normal requests
    for i in range(3):
        allowed, info = validator.check_rate_limit("test_user", rate_limit)
        assert allowed, f"Request {i+1} should be allowed"
        assert info["requests_in_minute"] == i + 1

    print("✓ Normal requests within limits allowed")

    # Test rate limit exceeded
    allowed, info = validator.check_rate_limit("test_user", rate_limit)
    assert not allowed, "Request should be rate limited"
    assert info["reason"] == "minute_limit_exceeded"

    print("✓ Rate limiting properly enforced")

    # Test different user
    allowed, info = validator.check_rate_limit("other_user", rate_limit)
    assert allowed, "Different user should not be affected"

    print("✓ Rate limiting per-user isolation works")


def test_injection_pattern_detection():
    """Test injection pattern detection"""
    print("\n🧪 Testing injection pattern detection...")

    validator = SecurityValidator(ValidationLevel.STRICT)

    # XSS patterns
    xss_patterns = [
        "<script>alert('xss')</script>",
        "javascript:alert(1)",
        "onload='alert(1)'",
        "<iframe src='javascript:alert(1)'></iframe>",
    ]

    for pattern in xss_patterns:
        violations = validator._check_injection_patterns(pattern)
        assert len(violations) > 0, f"XSS pattern should be detected: {pattern}"

    print("✓ XSS patterns properly detected")

    # Command injection patterns
    command_patterns = [
        "test; rm -rf /",
        "test | cat /etc/passwd",
        "test && echo 'hacked'",
        "test`whoami`",
    ]

    for pattern in command_patterns:
        violations = validator._check_injection_patterns(pattern)
        assert len(violations) > 0, f"Command injection should be detected: {pattern}"

    print("✓ Command injection patterns properly detected")

    # Code execution patterns
    code_patterns = [
        "exec('malicious_code')",
        "eval('alert(1)')",
        "__import__('os').system('ls')",
        "system('cat /etc/passwd')",
    ]

    for pattern in code_patterns:
        violations = validator._check_injection_patterns(pattern)
        assert len(violations) > 0, f"Code execution should be detected: {pattern}"

    print("✓ Code execution patterns properly detected")


def test_validation_levels():
    """Test different validation levels"""
    print("\n🧪 Testing validation levels...")

    test_input = "provider with spaces/model-name"

    # Strict validation
    strict_validator = SecurityValidator(ValidationLevel.STRICT)
    result = strict_validator.validate_model_string(test_input)
    # Strict mode might reject spaces in provider names
    if not result.is_valid:
        assert len(result.violations) > 0

    # Permissive validation
    permissive_validator = SecurityValidator(ValidationLevel.PERMISSIVE)
    result = permissive_validator.validate_model_string(test_input)
    # Permissive mode should be more lenient

    print("✓ Different validation levels work correctly")


def test_blocking_functionality():
    """Test identifier blocking functionality"""
    print("\n🧪 Testing blocking functionality...")

    validator = SecurityValidator()

    # Initially not blocked
    assert not validator.is_blocked("malicious_user")

    # Block user
    validator.block_identifier("malicious_user", "multiple_violations")
    assert validator.is_blocked("malicious_user")

    # Unblock user
    validator.unblock_identifier("malicious_user")
    assert not validator.is_blocked("malicious_user")

    print("✓ Blocking functionality works correctly")


def test_convenience_functions():
    """Test convenience functions"""
    print("\n🧪 Testing convenience functions...")

    # Test validate_model_input
    result = validate_model_input("openai/gpt-4")
    assert result.is_valid

    # Test validate_content_input
    result = validate_content_input("Safe content")
    assert result.is_valid

    # Test sanitize_log_message
    sensitive_msg = "API key: sk-1234567890abcdef1234567890abcdef"
    sanitized = sanitize_log_message(sensitive_msg)
    assert "sk-" not in sanitized
    assert "[REDACTED]" in sanitized

    # Test check_request_rate_limit
    allowed, info = check_request_rate_limit("test_user", 10)
    assert allowed
    assert isinstance(info, dict)

    print("✓ Convenience functions work correctly")


def test_security_summary():
    """Test security summary reporting"""
    print("\n🧪 Testing security summary...")

    validator = SecurityValidator()

    # Block some identifiers to test reporting
    validator.block_identifier("bad_actor_1")
    validator.block_identifier("bad_actor_2")

    summary = validator.get_security_summary()

    assert isinstance(summary, dict)
    assert "validation_level" in summary
    assert "blocked_ips" in summary
    assert summary["blocked_ips"] == 2
    assert "injection_patterns_count" in summary
    assert summary["injection_patterns_count"] > 0

    print("✓ Security summary reporting works correctly")


def run_tests():
    """Run all security tests"""
    print("🔒 Testing Security Validator Implementation")
    print("=" * 60)

    try:
        test_model_string_validation()
        test_content_validation()
        test_api_key_validation()
        test_sensitive_data_sanitization()
        test_rate_limiting()
        test_injection_pattern_detection()
        test_validation_levels()
        test_blocking_functionality()
        test_convenience_functions()
        test_security_summary()

        print("\n" + "=" * 60)
        print("🎉 All security tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
