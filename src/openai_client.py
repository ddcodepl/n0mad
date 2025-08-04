import os
import logging
import threading
import signal
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
import time
from config import DEFAULT_MODEL, REFINEMENT_PROMPT


load_dotenv()

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.max_retries = 3
        self.retry_delay = 1
        
        # Parse provider and model from format: provider/model
        if "/" in self.model:
            self.provider, self.actual_model = self.model.split("/", 1)
        else:
            self.provider = "openai"
            self.actual_model = self.model
        
        # Initialize client based on provider
        self._initialize_client(api_key)
    
    def _initialize_client(self, api_key: Optional[str] = None):
        """Initialize the appropriate client based on provider"""
        if self.provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            self.client = OpenAI(api_key=self.api_key)
        else:
            # For all other providers, use OpenRouter
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            if not self.api_key:
                raise ValueError("OpenRouter API key not found. Set OPENROUTER_API_KEY environment variable.")
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key
            )
    
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
                logger.info("Shutdown requested, aborting OpenAI processing")
                raise Exception("Processing aborted due to shutdown")
            
            try:
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
                            timeout=timeout  # Set OpenAI client timeout
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
                poll_interval = 0.5  # Check every 500ms
                elapsed_time = 0
                
                while api_thread.is_alive() and elapsed_time < timeout:
                    # Check for shutdown during API call
                    if shutdown_flag and shutdown_flag():
                        logger.info("Shutdown requested during OpenAI API call, aborting...")
                        # Note: We can't kill the thread, but we can abort and let it finish in background
                        raise Exception("Processing aborted due to shutdown")
                    
                    time.sleep(poll_interval)
                    elapsed_time += poll_interval
                
                # Wait for thread to complete (with small additional time)
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
        
        # Re-parse provider and model
        if "/" in self.model:
            self.provider, self.actual_model = self.model.split("/", 1)
        else:
            self.provider = "openai"
            self.actual_model = self.model
        
        # Re-initialize client with new provider if needed
        self._initialize_client()
        logger.info(f"Model set to: {model} (Provider: {self.provider}, Model: {self.actual_model})")