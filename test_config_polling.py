#!/usr/bin/env python3
"""
Test script for enhanced polling configuration management
Tests validation, environment variable loading, and edge cases
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import ConfigurationManager, MIN_POLLING_INTERVAL_MINUTES, MAX_POLLING_INTERVAL_MINUTES


def test_basic_functionality():
    """Test basic configuration functionality"""
    print("🧪 Testing basic configuration functionality...")
    
    # Clear environment variables first to test true defaults
    original_env = {}
    for key in ['ENABLE_CONTINUOUS_POLLING', 'POLLING_INTERVAL_MINUTES']:
        if key in os.environ:
            original_env[key] = os.environ[key]
            del os.environ[key]
    
    try:
        config = ConfigurationManager()
        
        # Test defaults (without environment variables)
        assert config.get_enable_continuous_polling() == False
        assert config.get_polling_interval_minutes() == 1
        assert config.validate_config() == True
        
        # Test setters
        config.set_enable_continuous_polling(True)
        assert config.get_enable_continuous_polling() == True
        
        config.set_polling_interval_minutes(5)
        assert config.get_polling_interval_minutes() == 5
        
    finally:
        # Restore environment variables
        for key, value in original_env.items():
            os.environ[key] = value
    
    print("✅ Basic functionality tests passed")


def test_validation_edge_cases():
    """Test validation with edge cases"""
    print("🧪 Testing validation edge cases...")
    
    config = ConfigurationManager()
    
    # Test minimum boundary
    config.set_polling_interval_minutes(MIN_POLLING_INTERVAL_MINUTES)
    assert config.get_polling_interval_minutes() == MIN_POLLING_INTERVAL_MINUTES
    assert config.validate_config() == True
    
    # Test maximum boundary
    config.set_polling_interval_minutes(MAX_POLLING_INTERVAL_MINUTES)
    assert config.get_polling_interval_minutes() == MAX_POLLING_INTERVAL_MINUTES
    assert config.validate_config() == True
    
    # Test invalid values
    try:
        config.set_polling_interval_minutes(0)  # Below minimum
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be >=" in str(e)
    
    try:
        config.set_polling_interval_minutes(MAX_POLLING_INTERVAL_MINUTES + 1)  # Above maximum
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be <=" in str(e)
    
    try:
        config.set_polling_interval_minutes("invalid")  # Wrong type
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be an integer" in str(e)
    
    try:
        config.set_enable_continuous_polling("invalid")  # Wrong type
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be a boolean" in str(e)
    
    print("✅ Validation edge cases tests passed")


def test_environment_variable_loading():
    """Test environment variable loading"""
    print("🧪 Testing environment variable loading...")
    
    # Save original environment variables
    original_env = {}
    for key in ['ENABLE_CONTINUOUS_POLLING', 'POLLING_INTERVAL_MINUTES']:
        if key in os.environ:
            original_env[key] = os.environ[key]
    
    try:
        # Set environment variables
        os.environ['ENABLE_CONTINUOUS_POLLING'] = 'true'
        os.environ['POLLING_INTERVAL_MINUTES'] = '10'
        
        config = ConfigurationManager()
        
        assert config.get_enable_continuous_polling() == True
        assert config.get_polling_interval_minutes() == 10
        
        # Test different boolean formats
        test_cases = [
            ('true', True),
            ('1', True),
            ('yes', True),
            ('on', True),
            ('false', False),
            ('0', False),
            ('no', False),
            ('off', False),
            ('anything_else', False)
        ]
        
        for env_value, expected in test_cases:
            os.environ['ENABLE_CONTINUOUS_POLLING'] = env_value
            config = ConfigurationManager()
            assert config.get_enable_continuous_polling() == expected, f"Failed for {env_value}"
        
        # Test invalid interval from environment
        os.environ['POLLING_INTERVAL_MINUTES'] = '0'
        try:
            config = ConfigurationManager()
            assert False, "Should have raised ValueError for invalid interval"
        except ValueError as e:
            # Check for either error message format
            assert ("Must be an integer between" in str(e) or "must be >=" in str(e)), f"Unexpected error: {e}"
        
        os.environ['POLLING_INTERVAL_MINUTES'] = 'invalid'
        try:
            config = ConfigurationManager()
            assert False, "Should have raised ValueError for non-integer"
        except ValueError as e:
            # Check for either error message format
            assert ("Must be an integer between" in str(e) or "invalid literal" in str(e)), f"Unexpected error: {e}"
    
    finally:
        # Clean up and restore original environment variables
        for key in ['ENABLE_CONTINUOUS_POLLING', 'POLLING_INTERVAL_MINUTES']:
            if key in os.environ:
                del os.environ[key]
        
        # Restore original values
        for key, value in original_env.items():
            os.environ[key] = value
    
    print("✅ Environment variable loading tests passed")


def test_helper_methods():
    """Test new helper methods"""
    print("🧪 Testing helper methods...")
    
    config = ConfigurationManager()
    
    # Test polling config summary
    summary = config.get_polling_config_summary()
    expected_keys = [
        'enable_continuous_polling', 'polling_interval_minutes', 
        'polling_interval_seconds', 'min_interval_minutes', 
        'max_interval_minutes', 'is_valid'
    ]
    
    for key in expected_keys:
        assert key in summary, f"Missing key: {key}"
    
    assert summary['polling_interval_seconds'] == summary['polling_interval_minutes'] * 60
    assert summary['min_interval_minutes'] == MIN_POLLING_INTERVAL_MINUTES
    assert summary['max_interval_minutes'] == MAX_POLLING_INTERVAL_MINUTES
    
    # Test is_polling_enabled
    config.set_enable_continuous_polling(False)
    assert config.is_polling_enabled() == False
    
    config.set_enable_continuous_polling(True)
    config.set_polling_interval_minutes(5)
    assert config.is_polling_enabled() == True
    
    # Test reset
    config.set_enable_continuous_polling(True)
    config.set_polling_interval_minutes(10)
    config.reset_polling_config()
    
    assert config.get_enable_continuous_polling() == False
    assert config.get_polling_interval_minutes() == 1
    
    print("✅ Helper methods tests passed")


def test_backward_compatibility():
    """Test backward compatibility with existing configuration"""
    print("🧪 Testing backward compatibility...")
    
    config = ConfigurationManager()
    
    # Test that all original methods still work
    assert hasattr(config, 'get_model')
    assert hasattr(config, 'set_model')
    assert hasattr(config, 'get_all_config')
    assert hasattr(config, 'update_config')
    
    # Test model configuration still works
    original_model = config.get_model()
    config.set_model('test-model')
    assert config.get_model() == 'test-model'
    config.set_model(original_model)
    
    # Test get_all_config includes new parameters
    all_config = config.get_all_config()
    assert 'enable_continuous_polling' in all_config
    assert 'polling_interval_minutes' in all_config
    assert 'model' in all_config
    
    # Test update_config with new parameters
    config.update_config({
        'enable_continuous_polling': True,
        'polling_interval_minutes': 15
    })
    
    assert config.get_enable_continuous_polling() == True
    assert config.get_polling_interval_minutes() == 15
    
    print("✅ Backward compatibility tests passed")


def main():
    """Run all tests"""
    print("🚀 Starting enhanced polling configuration tests...\n")
    
    try:
        test_basic_functionality()
        test_validation_edge_cases()
        test_environment_variable_loading()
        test_helper_methods()
        test_backward_compatibility()
        
        print("\n🎉 All tests passed successfully!")
        print("✅ Enhanced polling configuration is working correctly")
        
        # Demo the configuration
        print("\n📋 Configuration Demo:")
        config = ConfigurationManager()
        config.set_enable_continuous_polling(True)
        config.set_polling_interval_minutes(5)
        
        summary = config.get_polling_config_summary()
        print(f"   📊 Polling enabled: {summary['enable_continuous_polling']}")
        print(f"   ⏱️  Interval: {summary['polling_interval_minutes']} minutes ({summary['polling_interval_seconds']} seconds)")
        print(f"   📏 Valid range: {summary['min_interval_minutes']}-{summary['max_interval_minutes']} minutes")
        print(f"   ✅ Configuration valid: {summary['is_valid']}")
        print(f"   🔄 Ready for polling: {config.is_polling_enabled()}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)