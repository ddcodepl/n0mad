#!/usr/bin/env python3
"""
Test provider router functionality
"""

import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from provider_router import (
    ProviderRouter, RouteDecision, ProviderRouterError,
    route_ai_request
)


def test_route_determination():
    """Test routing decision logic"""
    print("🧪 Testing route determination...")
    
    router = ProviderRouter()
    
    # Mock config manager to control API key availability
    with patch('provider_router.config_manager') as mock_config:
        # Test OpenAI routing with API key available
        mock_config.has_api_key.side_effect = lambda provider: provider == 'openai'
        
        decision, parsed = router.determine_route("openai/gpt-4")
        assert decision == RouteDecision.OPENAI_DIRECT
        assert parsed.provider == "openai"
        assert parsed.model == "gpt-4"
        print("✓ OpenAI direct routing decision correct")
        
        # Test OpenRouter routing
        mock_config.has_api_key.side_effect = lambda provider: provider == 'openrouter'
        
        decision, parsed = router.determine_route("anthropic/claude-3-sonnet")
        assert decision == RouteDecision.OPENROUTER
        assert parsed.provider == "anthropic"
        assert parsed.model == "claude-3-sonnet"
        print("✓ OpenRouter routing decision correct")
        
        # Test fallback when OpenAI requested but only OpenRouter available
        mock_config.has_api_key.side_effect = lambda provider: provider == 'openrouter'
        
        decision, parsed = router.determine_route("openai/gpt-4")
        assert decision == RouteDecision.OPENROUTER
        print("✓ Fallback routing decision correct")


def test_invalid_model_handling():
    """Test handling of invalid model strings"""
    print("\n🧪 Testing invalid model handling...")
    
    router = ProviderRouter()
    
    with patch('provider_router.config_manager') as mock_config:
        mock_config.has_api_key.side_effect = lambda provider: provider == 'openai'
        
        # Test invalid model format
        decision, parsed = router.determine_route("invalid-model")
        assert decision == RouteDecision.FALLBACK
        assert parsed.provider == "openai"  # Default fallback
        assert parsed.model == "gpt-4o-mini"  # Default fallback
        print("✓ Invalid model format handled correctly")
        
        # Test None model
        decision, parsed = router.determine_route(None)
        assert decision == RouteDecision.OPENAI_DIRECT  # Should use default
        print("✓ None model handled correctly")


def test_no_api_keys_error():
    """Test error when no API keys are available"""
    print("\n🧪 Testing no API keys error...")
    
    router = ProviderRouter()
    
    with patch('provider_router.config_manager') as mock_config:
        # No API keys available
        mock_config.has_api_key.return_value = False
        
        try:
            router.determine_route("openai/gpt-4")
            assert False, "Should have raised ProviderRouterError"
        except ProviderRouterError as e:
            assert "No API keys available" in str(e)
            print("✓ No API keys error handled correctly")


@patch('provider_router.OpenAIClient')
def test_openai_routing(mock_openai_client):
    """Test OpenAI routing execution"""
    print("\n🧪 Testing OpenAI routing execution...")
    
    # Setup mock
    mock_client_instance = Mock()
    mock_client_instance.process_content.return_value = "OpenAI response"
    mock_openai_client.return_value = mock_client_instance
    
    router = ProviderRouter()
    
    with patch('provider_router.config_manager') as mock_config:
        mock_config.has_api_key.side_effect = lambda provider: provider == 'openai'
        
        response = router.route_request(
            model_string="openai/gpt-4",
            content="Test content",
            system_prompt="Test system prompt"
        )
        
        assert response == "OpenAI response"
        mock_openai_client.assert_called_once_with(model="openai/gpt-4")
        mock_client_instance.process_content.assert_called_once()
        
        # Check statistics
        stats = router.get_routing_statistics()
        assert stats['total_routes'] == 1
        assert stats['openai_routes'] == 1
        
        print("✓ OpenAI routing execution works correctly")


@patch('provider_router.OpenRouterClient')
def test_openrouter_routing(mock_openrouter_client):
    """Test OpenRouter routing execution"""
    print("\n🧪 Testing OpenRouter routing execution...")
    
    # Setup mock
    mock_client_instance = Mock()
    mock_client_instance.call_openrouter.return_value = "OpenRouter response"
    mock_openrouter_client.return_value = mock_client_instance
    
    router = ProviderRouter()
    
    with patch('provider_router.config_manager') as mock_config:
        mock_config.has_api_key.side_effect = lambda provider: provider == 'openrouter'
        
        response = router.route_request(
            model_string="anthropic/claude-3-sonnet",
            content="Test content",
            system_prompt="Test system prompt",
            temperature=0.7
        )
        
        assert response == "OpenRouter response"
        mock_openrouter_client.assert_called_once()
        mock_client_instance.call_openrouter.assert_called_once_with(
            model_name="anthropic/claude-3-sonnet",
            prompt="Test content",
            system_prompt="Test system prompt",
            shutdown_flag=None,
            temperature=0.7
        )
        
        # Check statistics
        stats = router.get_routing_statistics()
        assert stats['total_routes'] == 1
        assert stats['openrouter_routes'] == 1
        
        print("✓ OpenRouter routing execution works correctly")


def test_routing_error_handling():
    """Test error handling during routing"""
    print("\n🧪 Testing routing error handling...")
    
    router = ProviderRouter()
    
    with patch('provider_router.config_manager') as mock_config, \
         patch('provider_router.OpenAIClient') as mock_openai:
        
        mock_config.has_api_key.side_effect = lambda provider: provider == 'openai'
        
        # Make OpenAI client raise an error
        mock_openai.side_effect = Exception("OpenAI client error")
        
        try:
            router.route_request(
                model_string="openai/gpt-4",
                content="Test content"
            )
            assert False, "Should have raised ProviderRouterError"
        except ProviderRouterError as e:
            assert "OpenAI routing failed" in str(e)
            
            # Check error statistics
            stats = router.get_routing_statistics()
            assert stats['routing_errors'] == 1
            
            print("✓ Routing error handling works correctly")


def test_statistics_and_metrics():
    """Test statistics calculation and reporting"""
    print("\n🧪 Testing statistics and metrics...")
    
    router = ProviderRouter()
    
    # Simulate some routing operations
    router.routing_stats['total_routes'] = 10
    router.routing_stats['openai_routes'] = 6
    router.routing_stats['openrouter_routes'] = 3
    router.routing_stats['fallback_routes'] = 1
    router.routing_stats['routing_errors'] = 0
    
    with patch('provider_router.config_manager') as mock_config:
        mock_config.has_api_key.side_effect = lambda provider: provider in ['openai', 'openrouter']
        
        stats = router.get_routing_statistics()
        
        assert stats['total_routes'] == 10
        assert stats['openai_percentage'] == 60.0
        assert stats['openrouter_percentage'] == 30.0
        assert stats['fallback_percentage'] == 10.0
        assert stats['error_rate'] == 0.0
        assert stats['provider_availability']['openai'] is True
        assert stats['provider_availability']['openrouter'] is True
        
        print("✓ Statistics calculation works correctly")
        
        # Test reset
        router.reset_statistics()
        stats = router.get_routing_statistics()
        assert stats['total_routes'] == 0
        print("✓ Statistics reset works correctly")


def test_routing_test_function():
    """Test routing test functionality"""
    print("\n🧪 Testing routing test function...")
    
    router = ProviderRouter()
    
    with patch('provider_router.config_manager') as mock_config:
        mock_config.has_api_key.side_effect = lambda provider: provider == 'openai'
        
        # Test successful routing test
        result = router.test_routing("openai/gpt-4")
        
        assert result['success'] is True
        assert result['parsed_provider'] == 'openai'
        assert result['parsed_model'] == 'gpt-4'
        assert result['routing_decision'] == RouteDecision.OPENAI_DIRECT.value
        assert result['provider_availability']['openai'] is True
        
        print("✓ Routing test function works correctly")
        
        # Test invalid model
        result = router.test_routing("invalid-format")
        assert result['success'] is True  # Should succeed with fallback
        assert result['routing_decision'] == RouteDecision.FALLBACK.value
        
        print("✓ Invalid model test works correctly")


@patch('provider_router.provider_router')
def test_convenience_function(mock_router):
    """Test convenience function"""
    print("\n🧪 Testing convenience function...")
    
    mock_router.route_request.return_value = "Convenience response"
    
    response = route_ai_request(
        model_string="openai/gpt-4",
        content="Test content",
        temperature=0.5
    )
    
    assert response == "Convenience response"
    mock_router.route_request.assert_called_once_with(
        model_string="openai/gpt-4",
        content="Test content",
        system_prompt=None,
        shutdown_flag=None,
        timeout=120,
        ticket_context=None,
        temperature=0.5
    )
    
    print("✓ Convenience function works correctly")


def run_tests():
    """Run all tests"""
    print("🚏 Testing Provider Router Implementation")
    print("=" * 60)
    
    try:
        test_route_determination()
        test_invalid_model_handling()
        test_no_api_keys_error()
        test_openai_routing()
        test_openrouter_routing()
        test_routing_error_handling()
        test_statistics_and_metrics()
        test_routing_test_function()
        test_convenience_function()
        
        print("\n" + "=" * 60)
        print("🎉 All provider router tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)