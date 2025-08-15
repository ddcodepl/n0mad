#!/usr/bin/env python3
"""
Test OpenRouter client functionality
"""

import os
import sys
import threading
import time
from unittest.mock import MagicMock, Mock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from openrouter_client import (
    OpenRouterAuthenticationError,
    OpenRouterClient,
    OpenRouterError,
    OpenRouterRateLimitError,
    OpenRouterTimeoutError,
    call_openrouter,
)


def test_client_initialization():
    """Test OpenRouter client initialization"""
    print("🧪 Testing client initialization...")

    # Test without API key (should raise error)
    original_key = os.environ.get("OPENROUTER_API_KEY")
    if "OPENROUTER_API_KEY" in os.environ:
        del os.environ["OPENROUTER_API_KEY"]

    try:
        try:
            client = OpenRouterClient()
            assert False, "Should have raised authentication error"
        except OpenRouterAuthenticationError:
            print("✓ Correctly raises error when API key missing")

        # Test with API key
        test_key = "sk-or-test-key-1234567890abcdef"
        client = OpenRouterClient(api_key=test_key)
        assert client.api_key == test_key
        assert client.timeout == OpenRouterClient.DEFAULT_TIMEOUT
        assert client.max_retries == OpenRouterClient.DEFAULT_MAX_RETRIES
        print("✓ Client initialization with API key works")

        # Test with custom parameters
        client = OpenRouterClient(api_key=test_key, timeout=60, max_retries=5, retry_delay=2)
        assert client.timeout == 60
        assert client.max_retries == 5
        assert client.retry_delay == 2
        print("✓ Client initialization with custom parameters works")

    finally:
        # Restore original API key
        if original_key:
            os.environ["OPENROUTER_API_KEY"] = original_key


def test_error_handling():
    """Test error handling and categorization"""
    print("\n🧪 Testing error handling...")

    test_key = "sk-or-test-key-1234567890abcdef"
    client = OpenRouterClient(api_key=test_key)

    # Test authentication error handling
    auth_error = Exception("401 Unauthorized: Invalid API key")
    try:
        client._handle_api_error(auth_error, 0)
        assert False, "Should have raised OpenRouterAuthenticationError"
    except OpenRouterAuthenticationError:
        print("✓ Authentication errors handled correctly")

    # Test rate limit error handling
    rate_limit_error = Exception("429 Rate limit exceeded")
    try:
        client._handle_api_error(rate_limit_error, client.max_retries)  # Final attempt
        assert False, "Should have raised OpenRouterRateLimitError"
    except OpenRouterRateLimitError:
        print("✓ Rate limit errors handled correctly")

    # Test timeout error handling
    timeout_error = Exception("Request timeout after 120 seconds")
    try:
        client._handle_api_error(timeout_error, client.max_retries)  # Final attempt
        assert False, "Should have raised OpenRouterTimeoutError"
    except OpenRouterTimeoutError:
        print("✓ Timeout errors handled correctly")


def test_statistics_tracking():
    """Test statistics tracking functionality"""
    print("\n🧪 Testing statistics tracking...")

    test_key = "sk-or-test-key-1234567890abcdef"
    client = OpenRouterClient(api_key=test_key)

    # Initial stats should be zero
    stats = client.get_statistics()
    assert stats["total_requests"] == 0
    assert stats["successful_requests"] == 0
    assert stats["success_rate"] == 0.0
    print("✓ Initial statistics are correct")

    # Simulate some requests
    client.stats["total_requests"] = 10
    client.stats["successful_requests"] = 8
    client.stats["failed_requests"] = 2
    client.stats["total_response_time"] = 40.0
    client.stats["total_tokens_used"] = 1600

    stats = client.get_statistics()
    assert stats["success_rate"] == 80.0
    assert stats["failure_rate"] == 20.0
    assert stats["average_response_time"] == 5.0
    assert stats["average_tokens_per_request"] == 200.0
    print("✓ Statistics calculations are correct")

    # Test reset
    client.reset_statistics()
    stats = client.get_statistics()
    assert stats["total_requests"] == 0
    assert stats["successful_requests"] == 0
    print("✓ Statistics reset works correctly")


def test_model_list():
    """Test model listing functionality"""
    print("\n🧪 Testing model listing...")

    test_key = "sk-or-test-key-1234567890abcdef"
    client = OpenRouterClient(api_key=test_key)

    models = client.get_available_models()
    assert isinstance(models, list)
    assert len(models) > 0

    # Check that models have expected structure
    for model in models:
        assert "id" in model
        assert "name" in model
        assert "/" in model["id"]  # Should be in provider/model format

    print(f"✓ Retrieved {len(models)} available models")
    print(f"  Sample models: {[m['id'] for m in models[:3]]}")


@patch("openrouter_client.OpenAI")
def test_mocked_api_call(mock_openai_class):
    """Test API call with mocked OpenAI client"""
    print("\n🧪 Testing mocked API call...")

    # Setup mock
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    # Mock successful response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test response from OpenRouter"
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 50

    mock_client.chat.completions.create.return_value = mock_response

    # Test API call
    test_key = "sk-or-test-key-1234567890abcdef"
    client = OpenRouterClient(api_key=test_key)

    response = client.call_openrouter(
        model_name="anthropic/claude-3-sonnet",
        prompt="Test prompt",
        system_prompt="Test system prompt",
    )

    assert response == "Test response from OpenRouter"
    assert client.stats["successful_requests"] == 1
    assert client.stats["total_tokens_used"] == 50

    # Verify correct API call was made
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args[1]

    assert call_args["model"] == "anthropic/claude-3-sonnet"
    assert len(call_args["messages"]) == 2
    assert call_args["messages"][0]["role"] == "system"
    assert call_args["messages"][1]["role"] == "user"
    assert call_args["messages"][1]["content"] == "Test prompt"

    print("✓ Mocked API call works correctly")
    print(f"✓ Response: {response}")


def test_shutdown_handling():
    """Test shutdown flag handling"""
    print("\n🧪 Testing shutdown handling...")

    test_key = "sk-or-test-key-1234567890abcdef"
    client = OpenRouterClient(api_key=test_key)

    # Create shutdown flag that's initially False, then becomes True
    shutdown_requested = False

    def shutdown_flag():
        return shutdown_requested

    # Mock a slow API call to test shutdown during request
    with patch.object(client, "client") as mock_client:

        def slow_api_call(*args, **kwargs):
            time.sleep(0.1)  # Small delay to allow shutdown check
            if shutdown_requested:
                raise Exception("Request interrupted")
            return Mock(choices=[Mock(message=Mock(content="Response"))])

        mock_client.chat.completions.create.side_effect = slow_api_call

        # Start API call in thread and request shutdown
        def make_request():
            try:
                client.call_openrouter(model_name="test/model", prompt="test", shutdown_flag=shutdown_flag)
            except OpenRouterError as e:
                if "shutdown" in str(e).lower():
                    print("✓ Shutdown handling works during API call")
                else:
                    raise

        # Test immediate shutdown
        shutdown_requested = True
        try:
            client.call_openrouter(model_name="test/model", prompt="test", shutdown_flag=shutdown_flag)
            assert False, "Should have raised shutdown error"
        except OpenRouterError as e:
            assert "shutdown" in str(e).lower()
            print("✓ Immediate shutdown handling works")


def test_convenience_function():
    """Test convenience function"""
    print("\n🧪 Testing convenience function...")

    # Mock the call since we don't have real API key
    with patch("openrouter_client.OpenRouterClient") as mock_client_class:
        mock_client = Mock()
        mock_client.call_openrouter.return_value = "Convenience function response"
        mock_client_class.return_value = mock_client

        response = call_openrouter("test/model", "test prompt")
        assert response == "Convenience function response"

        # Verify client was created and method called
        mock_client_class.assert_called_once()
        mock_client.call_openrouter.assert_called_once_with("test/model", "test prompt", None)

        print("✓ Convenience function works correctly")


def run_tests():
    """Run all tests"""
    print("🔌 Testing OpenRouter Client Implementation")
    print("=" * 60)

    try:
        test_client_initialization()
        test_error_handling()
        test_statistics_tracking()
        test_model_list()
        test_mocked_api_call()
        test_shutdown_handling()
        test_convenience_function()

        print("\n" + "=" * 60)
        print("🎉 All OpenRouter client tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
