#!/usr/bin/env python3
"""
Provider Router Service

Implements routing layer to direct AI requests to appropriate provider (OpenAI or OpenRouter).
Provides a clean interface for routing decisions and handles provider-specific logic.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from enum import Enum

from utils.model_parser import ModelParser, ValidationError, ParsedModel
from clients.openai_client import OpenAIClient
from clients.openrouter_client import OpenRouterClient, OpenRouterError
from utils.config import config_manager
from utils.security_validator import security_validator, sanitize_log_message

logger = logging.getLogger(__name__)


class ProviderRouterError(Exception):
    """Base exception for provider routing errors"""
    pass


class RouteDecision(str, Enum):
    """Routing decision types"""
    OPENAI_DIRECT = "openai_direct"
    OPENROUTER = "openrouter"
    FALLBACK = "fallback"


class ProviderRouter:
    """
    Provider routing service that directs requests to appropriate AI providers.
    
    Handles model string parsing, provider selection, client initialization,
    and request routing with comprehensive error handling and logging.
    """
    
    def __init__(self):
        """Initialize the provider router"""
        self.routing_stats = {
            'total_routes': 0,
            'openai_routes': 0,
            'openrouter_routes': 0,
            'fallback_routes': 0,
            'routing_errors': 0
        }
        
        logger.info("Provider router initialized")
    
    def determine_route(self, model_string: Optional[str]) -> Tuple[RouteDecision, ParsedModel]:
        """
        Determine routing decision for a given model string.
        
        Args:
            model_string: Model string in provider/model format
            
        Returns:
            Tuple of (routing_decision, parsed_model)
            
        Raises:
            ProviderRouterError: If routing cannot be determined
        """
        try:
            # Parse the model string
            parsed = ModelParser.parse_model_string(model_string, strict_validation=False)
            
            # Check for critical validation errors
            if not parsed.is_valid:
                has_critical_errors = any("must contain '/'" in error for error in parsed.validation_errors)
                if has_critical_errors:
                    logger.warning(f"Critical validation errors in model '{model_string}', using fallback")
                    fallback_provider, fallback_model = ModelParser.get_default_model()
                    fallback_parsed = ParsedModel(fallback_provider, fallback_model, model_string or "default")
                    return RouteDecision.FALLBACK, fallback_parsed
            
            # Determine routing based on provider
            if ModelParser.is_openai_provider(parsed.provider):
                # Check if OpenAI API key is available
                if config_manager.has_api_key('openai'):
                    return RouteDecision.OPENAI_DIRECT, parsed
                else:
                    logger.warning("OpenAI provider requested but no API key available, trying OpenRouter")
                    if config_manager.has_api_key('openrouter'):
                        return RouteDecision.OPENROUTER, parsed
                    else:
                        raise ProviderRouterError("No API keys available for OpenAI or OpenRouter")
            else:
                # Non-OpenAI provider - use OpenRouter
                if config_manager.has_api_key('openrouter'):
                    return RouteDecision.OPENROUTER, parsed
                else:
                    logger.warning("OpenRouter API key not available, falling back to OpenAI")
                    if config_manager.has_api_key('openai'):
                        fallback_provider, fallback_model = ModelParser.get_default_model()
                        fallback_parsed = ParsedModel(fallback_provider, fallback_model, model_string or "default")
                        return RouteDecision.FALLBACK, fallback_parsed
                    else:
                        raise ProviderRouterError("No API keys available for requested provider or fallback")
                        
        except ValidationError as e:
            logger.error(f"Model validation failed: {e}")
            # Try fallback
            if config_manager.has_api_key('openai'):
                fallback_provider, fallback_model = ModelParser.get_default_model()
                fallback_parsed = ParsedModel(fallback_provider, fallback_model, model_string or "default")
                return RouteDecision.FALLBACK, fallback_parsed
            else:
                raise ProviderRouterError(f"Model validation failed and no fallback available: {e}")
    
    def route_request(self, 
                     model_string: Optional[str],
                     content: str,
                     system_prompt: Optional[str] = None,
                     shutdown_flag: Optional[callable] = None,
                     timeout: int = 120,
                     ticket_context: Optional[Dict[str, Any]] = None,
                     **kwargs) -> str:
        """
        Route a request to the appropriate provider and return the response.
        
        Args:
            model_string: Model string in provider/model format
            content: Content to process
            system_prompt: Optional system prompt
            shutdown_flag: Optional shutdown check function
            timeout: Request timeout in seconds
            ticket_context: Optional context for ticket processing
            **kwargs: Additional parameters for the provider
            
        Returns:
            Generated response text
            
        Raises:
            ProviderRouterError: If routing or processing fails
        """
        self.routing_stats['total_routes'] += 1
        
        try:
            # Security validation
            if model_string:
                model_validation = security_validator.validate_model_string(model_string)
                if not model_validation.is_valid:
                    logger.warning(f"Model string security validation failed: {model_validation.violations}")
                    raise ProviderRouterError(f"Invalid model string: {model_validation.violations}")
            
            if content:
                content_validation = security_validator.validate_content(content)
                if not content_validation.is_valid and content_validation.risk_level == "high":
                    logger.warning(f"Content security validation failed: {content_validation.violations}")
                    raise ProviderRouterError(f"Content validation failed: {content_validation.violations}")
                # Use sanitized content for processing
                content = content_validation.sanitized_input or content
            
            # Determine routing decision
            route_decision, parsed_model = self.determine_route(model_string)
            
            logger.info(f"Routing decision: {route_decision.value} for model '{sanitize_log_message(model_string or 'default')}' -> {parsed_model.provider}/{parsed_model.model}")
            
            # Route to appropriate provider
            if route_decision == RouteDecision.OPENAI_DIRECT:
                return self._route_to_openai(parsed_model, content, system_prompt, shutdown_flag, timeout, ticket_context, **kwargs)
            
            elif route_decision == RouteDecision.OPENROUTER:
                return self._route_to_openrouter(parsed_model, content, system_prompt, shutdown_flag, timeout, **kwargs)
            
            elif route_decision == RouteDecision.FALLBACK:
                return self._route_to_fallback(parsed_model, content, system_prompt, shutdown_flag, timeout, ticket_context, **kwargs)
            
            else:
                raise ProviderRouterError(f"Unknown routing decision: {route_decision}")
                
        except Exception as e:
            self.routing_stats['routing_errors'] += 1
            logger.error(f"Routing request failed: {e}")
            raise ProviderRouterError(f"Failed to route request: {e}")
    
    def _route_to_openai(self, 
                        parsed_model: ParsedModel,
                        content: str,
                        system_prompt: Optional[str],
                        shutdown_flag: Optional[callable],
                        timeout: int,
                        ticket_context: Optional[Dict[str, Any]],
                        **kwargs) -> str:
        """Route request to OpenAI direct client"""
        self.routing_stats['openai_routes'] += 1
        
        try:
            # Create OpenAI client with the specific model
            model_string = ModelParser.format_model_string(parsed_model.provider, parsed_model.model)
            client = OpenAIClient(model=model_string)
            
            # Process the request
            response = client.process_content(
                content=content,
                system_prompt=system_prompt,
                shutdown_flag=shutdown_flag,
                timeout=timeout,
                ticket_context=ticket_context
            )
            
            logger.info(f"OpenAI direct routing successful for {parsed_model.provider}/{parsed_model.model}")
            return response
            
        except Exception as e:
            logger.error(f"OpenAI direct routing failed: {e}")
            raise ProviderRouterError(f"OpenAI routing failed: {e}")
    
    def _route_to_openrouter(self,
                           parsed_model: ParsedModel,
                           content: str,
                           system_prompt: Optional[str],
                           shutdown_flag: Optional[callable],
                           timeout: int,
                           **kwargs) -> str:
        """Route request to OpenRouter client"""
        self.routing_stats['openrouter_routes'] += 1
        
        try:
            # Create OpenRouter client
            client = OpenRouterClient(timeout=timeout)
            
            # Format model name for OpenRouter
            model_name = ModelParser.format_model_string(parsed_model.provider, parsed_model.model)
            
            # Process the request
            response = client.call_openrouter(
                model_name=model_name,
                prompt=content,
                system_prompt=system_prompt,
                shutdown_flag=shutdown_flag,
                **kwargs
            )
            
            logger.info(f"OpenRouter routing successful for {parsed_model.provider}/{parsed_model.model}")
            return response
            
        except OpenRouterError as e:
            logger.error(f"OpenRouter routing failed: {e}")
            raise ProviderRouterError(f"OpenRouter routing failed: {e}")
        except Exception as e:
            logger.error(f"OpenRouter routing failed with unexpected error: {e}")
            raise ProviderRouterError(f"OpenRouter routing failed: {e}")
    
    def _route_to_fallback(self,
                          parsed_model: ParsedModel,
                          content: str,
                          system_prompt: Optional[str],
                          shutdown_flag: Optional[callable],
                          timeout: int,
                          ticket_context: Optional[Dict[str, Any]],
                          **kwargs) -> str:
        """Route request to fallback provider (usually OpenAI with default model)"""
        self.routing_stats['fallback_routes'] += 1
        
        logger.info(f"Using fallback routing for originally requested model: {parsed_model.original_string}")
        
        try:
            # Use default OpenAI model as fallback
            fallback_model = ModelParser.format_model_string(parsed_model.provider, parsed_model.model)
            client = OpenAIClient(model=fallback_model)
            
            # Process the request
            response = client.process_content(
                content=content,
                system_prompt=system_prompt,
                shutdown_flag=shutdown_flag,
                timeout=timeout,
                ticket_context=ticket_context
            )
            
            logger.info(f"Fallback routing successful using {parsed_model.provider}/{parsed_model.model}")
            return response
            
        except Exception as e:
            logger.error(f"Fallback routing failed: {e}")
            raise ProviderRouterError(f"Fallback routing failed: {e}")
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        """Get routing statistics and performance metrics"""
        stats = self.routing_stats.copy()
        
        # Calculate derived statistics
        if stats['total_routes'] > 0:
            stats['openai_percentage'] = (stats['openai_routes'] / stats['total_routes']) * 100
            stats['openrouter_percentage'] = (stats['openrouter_routes'] / stats['total_routes']) * 100
            stats['fallback_percentage'] = (stats['fallback_routes'] / stats['total_routes']) * 100
            stats['error_rate'] = (stats['routing_errors'] / stats['total_routes']) * 100
        else:
            stats['openai_percentage'] = 0.0
            stats['openrouter_percentage'] = 0.0
            stats['fallback_percentage'] = 0.0
            stats['error_rate'] = 0.0
        
        # Add provider availability info
        stats['provider_availability'] = {
            'openai': config_manager.has_api_key('openai'),
            'openrouter': config_manager.has_api_key('openrouter')
        }
        
        return stats
    
    def reset_statistics(self) -> None:
        """Reset routing statistics"""
        for key in self.routing_stats:
            self.routing_stats[key] = 0
        logger.info("Routing statistics reset")
    
    def test_routing(self, model_string: Optional[str]) -> Dict[str, Any]:
        """
        Test routing decision without making actual request.
        
        Args:
            model_string: Model string to test routing for
            
        Returns:
            Dictionary with routing test results
        """
        try:
            route_decision, parsed_model = self.determine_route(model_string)
            
            return {
                'success': True,
                'model_string': model_string,
                'parsed_provider': parsed_model.provider,
                'parsed_model': parsed_model.model,
                'routing_decision': route_decision.value,
                'is_valid': parsed_model.is_valid,
                'validation_errors': parsed_model.validation_errors,
                'provider_availability': {
                    'openai': config_manager.has_api_key('openai'),
                    'openrouter': config_manager.has_api_key('openrouter')
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'model_string': model_string,
                'error': str(e),
                'provider_availability': {
                    'openai': config_manager.has_api_key('openai'),
                    'openrouter': config_manager.has_api_key('openrouter')
                }
            }


# Global router instance
provider_router = ProviderRouter()


# Convenience function for direct usage
def route_ai_request(model_string: Optional[str],
                    content: str,
                    system_prompt: Optional[str] = None,
                    shutdown_flag: Optional[callable] = None,
                    timeout: int = 120,
                    ticket_context: Optional[Dict[str, Any]] = None,
                    **kwargs) -> str:
    """
    Convenience function to route an AI request through the provider router.
    
    Args:
        model_string: Model string in provider/model format
        content: Content to process
        system_prompt: Optional system prompt
        shutdown_flag: Optional shutdown check function
        timeout: Request timeout in seconds
        ticket_context: Optional context for ticket processing
        **kwargs: Additional parameters
        
    Returns:
        Generated response text
    """
    return provider_router.route_request(
        model_string=model_string,
        content=content,
        system_prompt=system_prompt,
        shutdown_flag=shutdown_flag,
        timeout=timeout,
        ticket_context=ticket_context,
        **kwargs
    )