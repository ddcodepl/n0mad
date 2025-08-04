#!/usr/bin/env python3
"""
Test integration of enhanced OpenAI client with OpenRouter support
"""

import os
import sys
from unittest.mock import Mock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from openai_client import OpenAIClient


def test_openai_model_initialization():
    """Test initialization with OpenAI model"""
    print("🧪 Testing OpenAI model initialization...")
    
    # Mock the OpenAI client to avoid requiring actual API key
    with patch('openai_client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Test with explicit OpenAI model
        client = OpenAIClient(api_key="sk-test-key", model="openai/gpt-4")
        
        assert client.provider == "openai"
        assert client.actual_model == "gpt-4"
        assert client.openrouter_client is None
        assert client.client is not None
        
        print("✓ OpenAI model initialization works correctly")


def test_openrouter_model_initialization():
    """Test initialization with non-OpenAI model (uses OpenRouter)"""
    print("\n🧪 Testing OpenRouter model initialization...")
    
    # Mock the OpenRouterClient to avoid requiring actual API key
    with patch('openai_client.OpenRouterClient') as mock_openrouter:
        mock_client = Mock()
        mock_openrouter.return_value = mock_client
        
        # Test with Anthropic model (should use OpenRouter)
        client = OpenAIClient(api_key="sk-or-test-key", model="anthropic/claude-3-sonnet")
        
        assert client.provider == "anthropic"
        assert client.actual_model == "claude-3-sonnet"
        assert client.openrouter_client is not None
        assert client.client is None
        
        print("✓ OpenRouter model initialization works correctly")


def test_model_validation():
    """Test model validation and fallback"""
    print("\n🧪 Testing model validation...")
    
    with patch('openai_client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Test with invalid model format
        client = OpenAIClient(api_key="sk-test-key", model="invalid-model-format")
        
        # Should fallback to default OpenAI model
        assert client.provider == "openai"
        assert client.actual_model == "gpt-4o-mini"
        
        print("✓ Model validation and fallback works correctly")


def test_model_switching():
    """Test switching between models/providers"""
    print("\n🧪 Testing model switching...")
    
    with patch('openai_client.OpenAI') as mock_openai, \
         patch('openai_client.OpenRouterClient') as mock_openrouter:
        
        mock_openai_client = Mock()
        mock_openrouter_client = Mock()
        mock_openai.return_value = mock_openai_client
        mock_openrouter.return_value = mock_openrouter_client
        
        # Start with OpenAI model
        client = OpenAIClient(api_key="sk-test-key", model="openai/gpt-4")
        assert client.provider == "openai"
        assert client.openrouter_client is None
        
        # Switch to Anthropic model (should initialize OpenRouter client)
        client.set_model("anthropic/claude-3-sonnet")
        assert client.provider == "anthropic"
        assert client.actual_model == "claude-3-sonnet"
        assert client.openrouter_client is not None
        
        # Switch back to OpenAI model
        client.set_model("openai/gpt-3.5-turbo")
        assert client.provider == "openai"
        assert client.actual_model == "gpt-3.5-turbo"
        assert client.openrouter_client is None
        
        print("✓ Model switching works correctly")


def test_statistics():
    """Test statistics retrieval"""
    print("\n🧪 Testing statistics...")
    
    with patch('openai_client.OpenRouterClient') as mock_openrouter:
        mock_client = Mock()
        mock_stats = {
            'total_requests': 10,
            'successful_requests': 9,
            'success_rate': 90.0
        }
        mock_client.get_statistics.return_value = mock_stats
        mock_openrouter.return_value = mock_client
        
        # Test with OpenRouter client
        client = OpenAIClient(api_key="sk-or-test-key", model="anthropic/claude-3-sonnet")
        stats = client.get_client_statistics()
        
        assert stats['provider'] == 'openrouter'
        assert stats['stats'] == mock_stats
        
        print("✓ Statistics retrieval works correctly")


def run_tests():
    """Run all integration tests"""
    print("🔧 Testing Enhanced OpenAI Client Integration")
    print("=" * 60)
    
    try:
        test_openai_model_initialization()
        test_openrouter_model_initialization()
        test_model_validation()
        test_model_switching()
        test_statistics()
        
        print("\n" + "=" * 60)
        print("🎉 All integration tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)