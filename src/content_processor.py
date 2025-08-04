import logging
from typing import Dict, Any, Optional, List
from notion_wrapper import NotionClientWrapper
from openai_client import OpenAIClient
from file_operations import FileOperations
from task_status import TaskStatus


logger = logging.getLogger(__name__)


class ContentProcessor:
    def __init__(self, notion_client: NotionClientWrapper, openai_client: OpenAIClient, file_ops: FileOperations):
        self.notion_client = notion_client
        self.default_openai_client = openai_client  # Keep default client for fallback
        self.file_ops = file_ops
    
    def process_task(self, task: Dict[str, Any], shutdown_flag: callable = None) -> Dict[str, Any]:
        # Guard against None tasks
        if task is None:
            logger.error("Received None task in process_task")
            return {
                "page_id": "unknown",
                "status": "failed",
                "error": "Task is None"
            }
        
        if not isinstance(task, dict):
            logger.error(f"Received invalid task type: {type(task)}")
            return {
                "page_id": "unknown", 
                "status": "failed",
                "error": f"Invalid task type: {type(task)}"
            }
        
        if "id" not in task:
            logger.error("Task missing required 'id' field")
            return {
                "page_id": "unknown",
                "status": "failed", 
                "error": "Task missing 'id' field"
            }
        
        page_id = task["id"]
        title = task.get("title", "Untitled")
        
        # Extract property ID from task properties if available
        property_id = None
        if "properties" in task and "ID" in task["properties"]:
            id_property = task["properties"]["ID"]
            if id_property.get("type") == "unique_id" and "unique_id" in id_property:
                unique_id = id_property["unique_id"]
                if unique_id is None:
                    logger.warning("unique_id is None in task properties")
                else:
                    prefix = unique_id.get("prefix", "")
                    number = unique_id.get("number", "")
                    property_id = f"{prefix}-{number}"
        
        # Use property_id as primary identifier if available, fallback to page_id
        task_id = property_id if property_id else page_id
        
        # Extract model from task properties if available
        model_to_use = None
        if "properties" in task and "Model" in task["properties"]:
            model_property = task["properties"]["Model"]
            if model_property.get("type") == "status" and "status" in model_property:
                status_obj = model_property["status"]
                if status_obj is not None:
                    model_to_use = status_obj.get("name")
                else:
                    logger.warning("Model property status is None")
            elif model_property.get("type") == "select" and "select" in model_property:
                select_obj = model_property["select"]
                if select_obj is not None:
                    model_to_use = select_obj.get("name")
                else:
                    logger.warning("Model property select is None")
            elif model_property.get("type") == "rich_text" and model_property.get("rich_text"):
                rich_text_list = model_property.get("rich_text")
                if rich_text_list and len(rich_text_list) > 0 and rich_text_list[0] is not None:
                    model_to_use = rich_text_list[0].get("plain_text")
                else:
                    logger.warning("Model property rich_text is None or empty")
        
        # Create appropriate OpenAI client based on model
        if model_to_use:
            logger.info(f"Using model from task properties: {model_to_use}")
            openai_client = OpenAIClient(model=model_to_use)
        else:
            logger.info("No model specified in task properties, using default client")
            openai_client = self.default_openai_client
        
        logger.info(f"Processing task: {title} (Task ID: {task_id}, Page ID: {page_id})")
        
        result = {
            "task_id": task_id,  # Primary clean identifier
            "page_id": page_id,  # Notion internal ID
            "property_id": property_id,  # Clean ID from properties
            "title": title,
            "status": "processing",
            "steps_completed": []
        }
        
        try:
            # Check for shutdown before starting
            if shutdown_flag and shutdown_flag():
                logger.info(f"Shutdown requested, aborting task processing for {page_id}")
                result["status"] = "aborted"
                result["message"] = "Processing aborted due to shutdown"
                return result
            
            logger.info(f"Step 1: Retrieving page content for {page_id}")
            page_content = self.notion_client.get_page_content(page_id)
            result["steps_completed"].append("content_retrieved")
            
            if not page_content.strip():
                logger.warning(f"Page {page_id} has no content to process")
                result["status"] = "skipped"
                result["message"] = "No content to process"
                return result
            
            # Check for shutdown before file operations
            if shutdown_flag and shutdown_flag():
                logger.info(f"Shutdown requested, aborting task processing for {page_id}")
                result["status"] = "aborted"
                result["message"] = "Processing aborted due to shutdown"
                return result
            
            logger.info(f"Step 2: Saving original content to pre-refined directory")
            pre_refined_path = self.file_ops.save_pre_refined(page_content, page_id, title, property_id)
            result["steps_completed"].append("pre_refined_saved")
            result["pre_refined_path"] = pre_refined_path
            
            # Check for shutdown before OpenAI processing (most time-consuming step)
            if shutdown_flag and shutdown_flag():
                logger.info(f"Shutdown requested, aborting task processing for {page_id}")
                result["status"] = "aborted"
                result["message"] = "Processing aborted due to shutdown"
                return result
            
            logger.info(f"Step 3: Sending content to OpenAI for processing")
            
            # Prepare ticket context for proper naming
            ticket_context = {
                "ticket_id": task_id,
                "page_id": page_id,
                "title": title,
                "stage": "pre-refined"
            }
            
            refined_content = openai_client.process_content(
                page_content, 
                shutdown_flag=shutdown_flag, 
                ticket_context=ticket_context
            )
            result["steps_completed"].append("content_processed")
            
            # Check for shutdown before final file operations
            if shutdown_flag and shutdown_flag():
                logger.info(f"Shutdown requested, aborting task processing for {page_id}")
                result["status"] = "aborted"
                result["message"] = "Processing aborted due to shutdown"
                return result
            
            logger.info(f"Step 4: Saving refined content to refined directory")
            refined_path = self.file_ops.save_refined(refined_content, page_id, title, property_id)
            result["steps_completed"].append("refined_saved")
            result["refined_path"] = refined_path
            
            # Check for shutdown before Notion updates
            if shutdown_flag and shutdown_flag():
                logger.info(f"Shutdown requested, aborting task processing for {page_id}")
                result["status"] = "aborted"
                result["message"] = "Processing aborted due to shutdown"
                return result
            
            logger.info(f"Step 5: Updating Notion page with refined content and status")
            self.notion_client.update_page_content(page_id, refined_content, TaskStatus.REFINED.value, shutdown_flag)
            result["steps_completed"].append("page_content_updated")
            result["steps_completed"].append("page_status_updated")
            
            result["status"] = "completed"
            logger.info(f"Successfully processed task: {title}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process task {page_id}: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
            
            try:
                logger.info(f"Attempting to update task status to 'Failed'")
                self.notion_client.update_page_status(page_id, TaskStatus.FAILED.value)
                result["steps_completed"].append("error_status_updated")
            except Exception as update_error:
                logger.error(f"Failed to update error status: {update_error}")
            
            return result
    
    def process_batch(self, tasks: List[Dict[str, Any]], shutdown_flag: callable = None) -> List[Dict[str, Any]]:
        results = []
        for task in tasks:
            # Check for shutdown before processing each task
            if shutdown_flag and shutdown_flag():
                logger.info(f"Shutdown requested, stopping batch processing after {len(results)} tasks")
                break
            
            result = self.process_task(task, shutdown_flag)
            results.append(result)
            
            # If task was aborted due to shutdown, stop processing
            if result.get("status") == "aborted":
                break
                
        return results