#!/usr/bin/env python3
"""
Test script to verify OpenRouter integration
"""
import sys
import os
from dotenv import load_dotenv

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from openai_client import OpenAIClient

load_dotenv()

def test_openai_model():
    """Test with OpenAI model"""
    print("Testing OpenAI model...")
    try:
        client = OpenAIClient(model="openai/gpt-4o-mini")
        
        ticket_context = {
            "ticket_id": "NOMAD-8",
            "page_id": "test-page-id",
            "title": "Add option to use openrouter with default open router",
            "stage": "pre-refined"
        }
        
        test_content = "We should extend current functionality to support OpenRouter as well as OpenAI"
        
        print(f"Provider: {client.provider}")
        print(f"Model: {client.actual_model}")
        print("Processing with OpenAI...")
        
        # This would require actual API keys, so we'll just test the initialization
        print("✅ OpenAI client initialized successfully")
        
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")

def test_openrouter_model():
    """Test with OpenRouter model"""
    print("\nTesting OpenRouter model...")
    try:
        client = OpenAIClient(model="anthropic/claude-3-5-sonnet-20241022")
        
        print(f"Provider: {client.provider}")
        print(f"Model: {client.actual_model}")
        print(f"Base URL: {client.client.base_url if hasattr(client.client, 'base_url') else 'N/A'}")
        
        print("✅ OpenRouter client initialized successfully")
        
    except Exception as e:
        print(f"❌ OpenRouter test failed: {e}")

def test_default_model():
    """Test with default model (no provider specified)"""
    print("\nTesting default model...")
    try:
        client = OpenAIClient(model="gpt-4o-mini")
        
        print(f"Provider: {client.provider}")
        print(f"Model: {client.actual_model}")
        
        print("✅ Default model client initialized successfully")
        
    except Exception as e:
        print(f"❌ Default model test failed: {e}")

if __name__ == "__main__":
    print("🧪 Testing OpenRouter Integration")
    print("=" * 50)
    
    test_openai_model()
    test_openrouter_model()
    test_default_model()
    
    print("\n" + "=" * 50)
    print("🏁 Test completed")