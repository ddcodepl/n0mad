import os
import logging
import threading
import signal
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
import time
from config import DEFAULT_MODEL, REFINEMENT_PROMPT
from openrouter_client import OpenRouterClient, OpenRouterError
from model_parser import ModelParser, ValidationError


load_dotenv()

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.max_retries = 3
        self.retry_delay = 1
        
        # Parse provider and model using enhanced parser
        try:
            parsed = ModelParser.parse_model_string(self.model, strict_validation=False)
            self.provider = parsed.provider
            self.actual_model = parsed.model
            
            if not parsed.is_valid:
                logger.warning(f"Model validation warnings for '{self.model}': {parsed.validation_errors}")
                # If there are critical validation errors, fallback to default
                has_critical_errors = any("must contain '/'" in error for error in parsed.validation_errors)
                if has_critical_errors:
                    logger.info(f"Critical validation errors detected, falling back to default model")
                    self.provider, self.actual_model = ModelParser.get_default_model()
                    logger.info(f"Using default model: {self.provider}/{self.actual_model}")
        except ValidationError as e:
            logger.error(f"Invalid model format '{self.model}': {e}")
            # Fallback to default
            self.provider, self.actual_model = ModelParser.get_default_model()
            logger.info(f"Using default model: {self.provider}/{self.actual_model}")
        
        # Initialize client based on provider
        self._initialize_client(api_key)
    
    def _initialize_client(self, api_key: Optional[str] = None):
        """Initialize the appropriate client based on provider"""
        if ModelParser.is_openai_provider(self.provider):
            # Use direct OpenAI client for OpenAI models
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            self.client = OpenAI(api_key=self.api_key)
            self.openrouter_client = None
            logger.info(f"Initialized OpenAI client for provider: {self.provider}")
        else:
            # Use dedicated OpenRouter client for all other providers
            openrouter_api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            if not openrouter_api_key:
                raise ValueError("OpenRouter API key not found. Set OPENROUTER_API_KEY environment variable.")
            
            self.openrouter_client = OpenRouterClient(
                api_key=openrouter_api_key,
                timeout=120,
                max_retries=self.max_retries,
                retry_delay=self.retry_delay
            )
            self.client = None  # Not using standard OpenAI client
            self.api_key = openrouter_api_key
            logger.info(f"Initialized OpenRouter client for provider: {self.provider}")
    
    def process_content(self, content: str, system_prompt: Optional[str] = None, shutdown_flag: callable = None, timeout: int = 120, ticket_context: Optional[Dict[str, Any]] = None) -> str:
        if system_prompt is None:
            system_prompt = REFINEMENT_PROMPT
        
        # Include ticket context in the system prompt if provided
        if ticket_context:
            context_info = f"\n\nTICKET CONTEXT FOR PROPER NAMING:\n"
            if ticket_context.get('ticket_id'):
                context_info += f"- Ticket ID: {ticket_context['ticket_id']}\n"
            if ticket_context.get('page_id'):
                context_info += f"- Page ID: {ticket_context['page_id']}\n"
            if ticket_context.get('title'):
                context_info += f"- Original Title: {ticket_context['title']}\n"
            if ticket_context.get('stage'):
                context_info += f"- Current Stage: {ticket_context['stage']}\n"
            
            context_info += "\nUse this context to properly format the ticket ID and title in your response."
            system_prompt += context_info
        
        for attempt in range(self.max_retries):
            # Check for shutdown before each attempt
            if shutdown_flag and shutdown_flag():
                logger.info("Shutdown requested, aborting AI processing")
                raise Exception("Processing aborted due to shutdown")
            
            try:
                if self.openrouter_client:
                    # Use OpenRouter client for non-OpenAI providers
                    logger.info(f"Starting OpenRouter API call (attempt {attempt + 1}/{self.max_retries}) with model: {self.actual_model}")
                    response = self.openrouter_client.call_openrouter(
                        model_name=self.actual_model,
                        prompt=content,
                        system_prompt=system_prompt,
                        shutdown_flag=shutdown_flag
                    )
                    logger.info("OpenRouter processing completed successfully")
                    return response
                else:
                    # Use direct OpenAI client
                    logger.info(f"Starting OpenAI API call (attempt {attempt + 1}/{self.max_retries}) with {timeout}s timeout...")
                    
                    # Use threading to make the API call interruptible
                    result = {"response": None, "error": None, "completed": False}
                    
                    def api_call():
                        try:
                            response = self.client.chat.completions.create(
                                model=self.actual_model,
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": content}
                                ],
                                timeout=timeout
                            )
                            result["response"] = response.choices[0].message.content
                            result["completed"] = True
                        except Exception as e:
                            result["error"] = e
                            result["completed"] = True
                    
                    # Start the API call in a separate thread
                    api_thread = threading.Thread(target=api_call, daemon=True)
                    api_thread.start()
                    
                    # Poll for completion while checking shutdown flag
                    poll_interval = 0.5
                    elapsed_time = 0
                    
                    while api_thread.is_alive() and elapsed_time < timeout:
                        if shutdown_flag and shutdown_flag():
                            logger.info("Shutdown requested during OpenAI API call, aborting...")
                            raise Exception("Processing aborted due to shutdown")
                        
                        time.sleep(poll_interval)
                        elapsed_time += poll_interval
                    
                    # Wait for thread to complete
                    api_thread.join(timeout=2.0)
                    
                    if not result["completed"]:
                        raise Exception(f"OpenAI API call timed out after {timeout} seconds")
                    
                    if result["error"]:
                        raise result["error"]
                    
                    if result["response"]:
                        logger.info("OpenAI processing completed successfully")
                        return result["response"]
                    else:
                        raise Exception("OpenAI API returned empty response")
                
            except Exception as e:
                logger.error(f"OpenAI API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    
                    # Sleep with shutdown checking
                    for i in range(int(wait_time)):
                        if shutdown_flag and shutdown_flag():
                            logger.info("Shutdown requested during retry delay, aborting...")
                            raise Exception("Processing aborted due to shutdown")
                        time.sleep(1)
                else:
                    raise Exception(f"Failed to process content after {self.max_retries} attempts: {e}")
    
    def set_model(self, model: str):
        self.model = model
        
        # Re-parse provider and model using enhanced parser
        try:
            parsed = ModelParser.parse_model_string(self.model, strict_validation=False)
            self.provider = parsed.provider
            self.actual_model = parsed.model
            
            if not parsed.is_valid:
                logger.warning(f"Model validation warnings for '{self.model}': {parsed.validation_errors}")
                # If there are critical validation errors, fallback to default
                has_critical_errors = any("must contain '/'" in error for error in parsed.validation_errors)
                if has_critical_errors:
                    logger.info(f"Critical validation errors detected, falling back to default model")
                    self.provider, self.actual_model = ModelParser.get_default_model()
                    logger.info(f"Using default model: {self.provider}/{self.actual_model}")
        except ValidationError as e:
            logger.error(f"Invalid model format '{self.model}': {e}")
            # Fallback to default
            self.provider, self.actual_model = ModelParser.get_default_model()
            logger.info(f"Using default model: {self.provider}/{self.actual_model}")
        
        # Re-initialize client with new provider if needed
        self._initialize_client()
        logger.info(f"Model set to: {model} (Provider: {self.provider}, Model: {self.actual_model})")
    
    def get_client_statistics(self) -> Dict[str, Any]:
        """Get statistics from the underlying client"""
        if self.openrouter_client:
            return {
                "provider": "openrouter",
                "stats": self.openrouter_client.get_statistics()
            }
        else:
            return {
                "provider": "openai",
                "stats": {
                    "note": "OpenAI client statistics not tracked in current implementation"
                }
            }