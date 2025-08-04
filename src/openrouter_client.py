#!/usr/bin/env python3
"""
OpenRouter API Client

Provides a dedicated client for OpenRouter API following existing OpenAI client patterns.
Supports connection pooling, timeout settings, retry logic, and comprehensive error handling.
"""

import os
import logging
import threading
import time
import json
from typing import Optional, Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors"""
    pass


class OpenRouterAuthenticationError(OpenRouterError):
    """Authentication error with OpenRouter API"""
    pass


class OpenRouterRateLimitError(OpenRouterError):
    """Rate limiting error from OpenRouter API"""
    pass


class OpenRouterTimeoutError(OpenRouterError):
    """Timeout error for OpenRouter API requests"""
    pass


class OpenRouterClient:
    """
    Dedicated OpenRouter API client with comprehensive error handling and monitoring.
    
    Follows existing OpenAI client patterns for consistency with the codebase.
    """
    
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    # Default configuration
    DEFAULT_TIMEOUT = 120
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1
    
    # OpenRouter-specific headers and configuration
    OPENROUTER_HEADERS = {
        "HTTP-Referer": "https://github.com/your-org/nomad-developer",  # Replace with actual repo
        "X-Title": "Nomad Developer - AI Task Processing"
    }
    
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 timeout: int = DEFAULT_TIMEOUT,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 retry_delay: int = DEFAULT_RETRY_DELAY):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise OpenRouterAuthenticationError("OpenRouter API key not found. Set OPENROUTER_API_KEY environment variable.")
        
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize OpenAI client configured for OpenRouter
        self.client = self._initialize_client()
        
        # Statistics tracking
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'timeout_requests': 0,
            'rate_limit_errors': 0,
            'auth_errors': 0,
            'total_tokens_used': 0,
            'total_response_time': 0.0
        }
        
        logger.info(f"OpenRouter client initialized with timeout={timeout}s, max_retries={max_retries}")
    
    def _initialize_client(self) -> OpenAI:
        """Initialize OpenAI client configured for OpenRouter"""
        try:
            # Create client with OpenRouter configuration
            client = OpenAI(
                base_url=self.OPENROUTER_BASE_URL,
                api_key=self.api_key,
                timeout=self.timeout,
                default_headers=self.OPENROUTER_HEADERS
            )
            
            logger.info("OpenRouter client initialized successfully")
            return client
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter client: {e}")
            raise OpenRouterError(f"Client initialization failed: {e}")
    
    def call_openrouter(self, 
                       model_name: str, 
                       prompt: str, 
                       system_prompt: Optional[str] = None,
                       shutdown_flag: Optional[callable] = None,
                       **kwargs) -> str:
        """
        Make a request to OpenRouter API with specified model and prompt.
        
        Args:
            model_name: Model identifier (e.g., 'anthropic/claude-3-sonnet')
            prompt: User prompt text
            system_prompt: Optional system prompt
            shutdown_flag: Optional callable to check for shutdown requests
            **kwargs: Additional parameters for the API call
            
        Returns:
            Generated response text
            
        Raises:
            OpenRouterError: For various API errors
            OpenRouterTimeoutError: For timeout errors
            OpenRouterRateLimitError: For rate limiting errors
            OpenRouterAuthenticationError: For authentication errors
        """
        self.stats['total_requests'] += 1
        start_time = time.time()
        
        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Prepare request parameters
        request_params = {
            'model': model_name,
            'messages': messages,
            'timeout': self.timeout,
            **kwargs  # Allow additional parameters like temperature, max_tokens, etc.
        }
        
        # Attempt request with retry logic
        for attempt in range(self.max_retries):
            # Check for shutdown before each attempt
            if shutdown_flag and shutdown_flag():
                logger.info("Shutdown requested, aborting OpenRouter processing")
                raise OpenRouterError("Processing aborted due to shutdown")
            
            try:
                logger.info(f"Making OpenRouter API call (attempt {attempt + 1}/{self.max_retries}) to model: {model_name}")
                
                # Use threading for interruptible requests
                result = {"response": None, "error": None, "completed": False}
                
                def api_call():
                    try:
                        response = self.client.chat.completions.create(**request_params)
                        result["response"] = response
                        result["completed"] = True
                    except Exception as e:
                        result["error"] = e
                        result["completed"] = True
                
                # Start API call in separate thread
                api_thread = threading.Thread(target=api_call, daemon=True)
                api_thread.start()
                
                # Poll for completion while checking shutdown flag
                poll_interval = 0.5
                elapsed_time = 0
                
                while api_thread.is_alive() and elapsed_time < self.timeout:
                    if shutdown_flag and shutdown_flag():
                        logger.info("Shutdown requested during OpenRouter API call, aborting...")
                        raise OpenRouterError("Processing aborted due to shutdown")
                    
                    time.sleep(poll_interval)
                    elapsed_time += poll_interval
                
                # Wait for thread completion
                api_thread.join(timeout=2.0)
                
                if not result["completed"]:
                    self.stats['timeout_requests'] += 1
                    raise OpenRouterTimeoutError(f"OpenRouter API call timed out after {self.timeout} seconds")
                
                if result["error"]:
                    raise result["error"]
                
                if result["response"]:
                    response = result["response"]
                    response_text = response.choices[0].message.content
                    
                    # Update statistics
                    self.stats['successful_requests'] += 1
                    self.stats['total_response_time'] += time.time() - start_time
                    
                    # Track token usage if available
                    if hasattr(response, 'usage') and response.usage:
                        if hasattr(response.usage, 'total_tokens'):
                            self.stats['total_tokens_used'] += response.usage.total_tokens
                    
                    logger.info(f"OpenRouter API call successful for model: {model_name}")
                    return response_text
                else:
                    raise OpenRouterError("OpenRouter API returned empty response")
                
            except Exception as e:
                self._handle_api_error(e, attempt)
                
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying OpenRouter request in {wait_time} seconds...")
                    
                    # Sleep with shutdown checking
                    for i in range(int(wait_time)):
                        if shutdown_flag and shutdown_flag():
                            logger.info("Shutdown requested during retry delay, aborting...")
                            raise OpenRouterError("Processing aborted due to shutdown")
                        time.sleep(1)
                else:
                    self.stats['failed_requests'] += 1
                    raise OpenRouterError(f"Failed to process OpenRouter request after {self.max_retries} attempts: {e}")
    
    def _handle_api_error(self, error: Exception, attempt: int) -> None:
        """Handle and categorize API errors for proper logging and statistics"""
        error_msg = str(error).lower()
        
        if "unauthorized" in error_msg or "invalid api key" in error_msg or "401" in error_msg:
            self.stats['auth_errors'] += 1
            logger.error(f"OpenRouter authentication error (attempt {attempt + 1}): {error}")
            if attempt == 0:  # Don't retry auth errors
                raise OpenRouterAuthenticationError(f"Authentication failed: {error}")
        
        elif "rate limit" in error_msg or "429" in error_msg:
            self.stats['rate_limit_errors'] += 1
            logger.warning(f"OpenRouter rate limit hit (attempt {attempt + 1}): {error}")
            if attempt >= self.max_retries - 1:
                raise OpenRouterRateLimitError(f"Rate limit exceeded: {error}")
        
        elif "timeout" in error_msg:
            self.stats['timeout_requests'] += 1
            logger.warning(f"OpenRouter timeout (attempt {attempt + 1}): {error}")
            if attempt >= self.max_retries - 1:
                raise OpenRouterTimeoutError(f"Request timeout: {error}")
        
        else:
            logger.error(f"OpenRouter API error (attempt {attempt + 1}): {error}")
            if attempt >= self.max_retries - 1:
                raise OpenRouterError(f"API error: {error}")
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models from OpenRouter.
        
        Returns:
            List of model dictionaries with model information
        """
        try:
            logger.info("Fetching available models from OpenRouter...")
            
            # Note: This would require a separate HTTP request to OpenRouter's models endpoint
            # For now, return a static list of commonly available models
            models = [
                {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus"},
                {"id": "anthropic/claude-3-sonnet", "name": "Claude 3 Sonnet"},
                {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku"},
                {"id": "anthropic/claude-3-5-sonnet", "name": "Claude 3.5 Sonnet"},
                {"id": "openai/gpt-4", "name": "GPT-4"},
                {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo"},
                {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
                {"id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
                {"id": "google/gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
                {"id": "mistralai/mistral-large", "name": "Mistral Large"},
                {"id": "meta-llama/llama-3.1-405b", "name": "Llama 3.1 405B"},
            ]
            
            logger.info(f"Retrieved {len(models)} available models")
            return models
            
        except Exception as e:
            logger.error(f"Failed to fetch available models: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get client usage statistics"""
        stats = self.stats.copy()
        
        # Calculate derived statistics
        if stats['total_requests'] > 0:
            stats['success_rate'] = (stats['successful_requests'] / stats['total_requests']) * 100
            stats['failure_rate'] = (stats['failed_requests'] / stats['total_requests']) * 100
        else:
            stats['success_rate'] = 0.0
            stats['failure_rate'] = 0.0
        
        if stats['successful_requests'] > 0:
            stats['average_response_time'] = stats['total_response_time'] / stats['successful_requests']
            stats['average_tokens_per_request'] = stats['total_tokens_used'] / stats['successful_requests']
        else:
            stats['average_response_time'] = 0.0
            stats['average_tokens_per_request'] = 0.0
        
        return stats
    
    def reset_statistics(self) -> None:
        """Reset client statistics"""
        for key in self.stats:
            if isinstance(self.stats[key], (int, float)):
                self.stats[key] = 0
        
        logger.info("OpenRouter client statistics reset")
    
    def test_connection(self) -> bool:
        """
        Test connection to OpenRouter API with a simple request.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Testing OpenRouter API connection...")
            
            # Make a simple test request
            response = self.call_openrouter(
                model_name="openai/gpt-3.5-turbo",
                prompt="Say 'Connection test successful' if you can read this.",
                timeout=30
            )
            
            if "successful" in response.lower():
                logger.info("✅ OpenRouter API connection test successful")
                return True
            else:
                logger.warning(f"⚠️ OpenRouter API connection test got unexpected response: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ OpenRouter API connection test failed: {e}")
            return False


# Convenience function for backward compatibility
def call_openrouter(model_name: str, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
    """
    Convenience function to make OpenRouter API calls.
    Creates a new client instance for each call.
    
    Args:
        model_name: Model identifier
        prompt: User prompt
        system_prompt: Optional system prompt
        **kwargs: Additional API parameters
        
    Returns:
        Generated response text
    """
    client = OpenRouterClient()
    return client.call_openrouter(model_name, prompt, system_prompt, **kwargs)