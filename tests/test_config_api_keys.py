#!/usr/bin/env python3
"""
Test enhanced configuration API key management
"""

import os
import sys
import tempfile

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import ConfigurationManager


def test_api_key_loading():
    """Test API key loading from environment"""
    print("🧪 Testing API key loading...")
    
    # Set some test environment variables
    test_env = {
        'OPENAI_API_KEY': 'sk-test-openai-key-1234567890',
        'OPENROUTER_API_KEY': 'sk-or-test-openrouter-key-1234567890',
        'ANTHROPIC_API_KEY': 'sk-ant-test-anthropic-key-1234567890'
    }
    
    # Temporarily set environment variables
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        # Create new configuration manager
        config = ConfigurationManager()
        
        # Test API key retrieval
        assert config.has_api_key('openai'), "Should have OpenAI API key"
        assert config.has_api_key('openrouter'), "Should have OpenRouter API key"
        assert config.has_api_key('anthropic'), "Should have Anthropic API key"
        assert not config.has_api_key('google'), "Should not have Google API key"
        
        # Test API key values
        assert config.get_api_key('openai') == test_env['OPENAI_API_KEY']
        assert config.get_api_key('openrouter') == test_env['OPENROUTER_API_KEY']
        assert config.get_api_key('anthropic') == test_env['ANTHROPIC_API_KEY']
        assert config.get_api_key('google') is None
        
        # Test available providers
        available = config.get_available_providers()
        assert 'openai' in available
        assert 'openrouter' in available
        assert 'anthropic' in available
        assert 'google' not in available
        
        print("✓ API key loading works correctly")
        
        # Test API key validation
        assert config.validate_api_key_format('sk-test-1234567890'), "Should be valid API key format"
        assert not config.validate_api_key_format('short'), "Should be invalid - too short"
        assert not config.validate_api_key_format('your_key_here'), "Should be invalid - placeholder"
        assert not config.validate_api_key_format(''), "Should be invalid - empty"
        
        print("✓ API key validation works correctly")
        
        # Test API key status
        status = config.get_api_key_status()
        assert status['openai']['available'] is True
        assert status['openai']['valid_format'] is True
        assert status['google']['available'] is False
        assert status['google']['valid_format'] is False
        
        print("✓ API key status reporting works correctly")
        
        # Test provider availability validation
        assert config.validate_provider_availability('openai') is True
        assert config.validate_provider_availability('google') is False
        
        print("✓ Provider availability validation works correctly")
        
    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is not None:
                os.environ[key] = original_value
            elif key in os.environ:
                del os.environ[key]


def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\n🧪 Testing edge cases...")
    
    # Test with empty/invalid API keys
    test_env = {
        'OPENAI_API_KEY': '',  # Empty
        'OPENROUTER_API_KEY': '   ',  # Whitespace only
        'ANTHROPIC_API_KEY': 'your_key_here',  # Placeholder
    }
    
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        config = ConfigurationManager()
        
        # All should be considered unavailable due to invalid format
        assert not config.has_api_key('openai'), "Empty key should not be available"
        assert not config.has_api_key('openrouter'), "Whitespace key should not be available"
        assert config.has_api_key('anthropic'), "Placeholder key should be available but invalid format"
        
        # But provider validation should catch the invalid format
        assert not config.validate_provider_availability('anthropic'), "Placeholder key should fail validation"
        
        print("✓ Edge cases handled correctly")
        
    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is not None:
                os.environ[key] = original_value
            elif key in os.environ:
                del os.environ[key]


def run_tests():
    """Run all tests"""
    print("🔑 Testing Enhanced Configuration API Key Management")
    print("=" * 60)
    
    try:
        test_api_key_loading()
        test_edge_cases()
        
        print("\n" + "=" * 60)
        print("🎉 All configuration tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)