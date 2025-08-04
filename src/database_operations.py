from typing import List, Dict, Any
from notion_wrapper import NotionClientWrapper
from task_status import TaskStatus
from logging_config import get_logger, log_key_value


logger = get_logger(__name__)


class DatabaseOperations:
    def __init__(self, notion_client: NotionClientWrapper):
        self.notion_client = notion_client
    
    def get_tasks_to_refine(self) -> List[Dict[str, Any]]:
        logger.info("🔍 Polling database for tasks with 'To Refine' status...")
        
        try:
            # Use dynamic filter creation based on actual property type
            filter_dict = self.notion_client.create_status_filter(TaskStatus.TO_REFINE.value)
            response = self.notion_client.query_database(filter_dict)
            
            # Extract results from the response
            tasks = response.get("results", []) if isinstance(response, dict) else []
            log_key_value(logger, "📊 Found tasks to refine", str(len(tasks)))
            
            task_list = []
            for task in tasks:
                try:
                    # Guard against None or invalid task objects
                    if task is None:
                        logger.warning("⚠️ Skipping None task in database response")
                        continue
                    
                    if not isinstance(task, dict):
                        logger.warning(f"⚠️ Skipping invalid task type: {type(task)}")
                        continue
                    
                    if "id" not in task:
                        logger.warning("⚠️ Skipping task without ID field")
                        continue
                    
                    task_info = {
                        "id": task["id"],
                        "url": task.get("url", ""),
                        "properties": task.get("properties", {}),
                        "created_time": task.get("created_time", ""),
                        "last_edited_time": task.get("last_edited_time", "")
                    }
                    
                    # Safely extract title
                    properties = task.get("properties", {})
                    if "Name" in properties and properties["Name"].get("title"):
                        title_list = properties["Name"]["title"]
                        if title_list and len(title_list) > 0:
                            task_info["title"] = title_list[0].get("plain_text", "Untitled")
                        else:
                            task_info["title"] = "Untitled"
                    else:
                        task_info["title"] = "Untitled"
                    
                    task_list.append(task_info)
                    logger.debug(f"📄 Added task: {task_info['title']} (ID: {task_info['id'][:8]}...)")
                    
                except Exception as task_error:
                    logger.error(f"❌ Error processing individual task: {task_error}")
                    continue
            
            return task_list
            
        except Exception as e:
            logger.error(f"❌ Failed to query tasks to refine: {e}")
            raise
    
    def get_task_by_status(self, status: TaskStatus) -> List[Dict[str, Any]]:
        logger.info(f"🔍 Querying database for tasks with '{status.value}' status...")
        
        try:
            # Use dynamic filter creation based on actual property type
            filter_dict = self.notion_client.create_status_filter(status.value)
            response = self.notion_client.query_database(filter_dict)
            
            # Extract results from the response
            tasks = response.get("results", []) if isinstance(response, dict) else []
            log_key_value(logger, f"📊 Found tasks with status '{status.value}'", str(len(tasks)))
            return tasks
        except Exception as e:
            logger.error(f"❌ Failed to query tasks with status '{status.value}': {e}")
            raise
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        logger.info("🔍 Retrieving all tasks from database...")
        
        try:
            response = self.notion_client.query_database()
            
            # Extract results from the response
            tasks = response.get("results", []) if isinstance(response, dict) else []
            log_key_value(logger, "📊 Retrieved total tasks", str(len(tasks)))
            return tasks
        except Exception as e:
            logger.error(f"❌ Failed to retrieve all tasks: {e}")
            raise
    
    def get_queued_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all tickets with 'Queued to run' status.
        
        Returns:
            List of ticket dictionaries with ID, properties, and metadata
        """
        logger.info("🔍 Detecting tickets with 'Queued to run' status...")
        
        try:
            # Use the existing get_task_by_status method with QUEUED_TO_RUN status
            queued_tasks = self.get_task_by_status(TaskStatus.QUEUED_TO_RUN)
            
            # Process and extract relevant information from queued tasks
            processed_tasks = []
            for task in queued_tasks:
                try:
                    # Guard against None or invalid task objects
                    if task is None:
                        logger.warning("⚠️ Skipping None task in queued tasks response")
                        continue
                    
                    if not isinstance(task, dict):
                        logger.warning(f"⚠️ Skipping invalid task type: {type(task)}")
                        continue
                    
                    if "id" not in task:
                        logger.warning("⚠️ Skipping queued task without ID field")
                        continue
                    
                    task_info = {
                        "id": task["id"],
                        "url": task.get("url", ""),
                        "properties": task.get("properties", {}),
                        "created_time": task.get("created_time", ""),
                        "last_edited_time": task.get("last_edited_time", ""),
                        "status": TaskStatus.QUEUED_TO_RUN.value
                    }
                    
                    # Safely extract title and ticket ID
                    properties = task.get("properties", {})
                    if "Name" in properties and properties["Name"].get("title"):
                        title_list = properties["Name"]["title"]
                        if title_list and len(title_list) > 0:
                            task_info["title"] = title_list[0].get("plain_text", "Untitled")
                        else:
                            task_info["title"] = "Untitled"
                    else:
                        task_info["title"] = "Untitled"
                    
                    # Extract ticket ID using existing logic from NotionClientWrapper
                    ticket_ids = self.notion_client.extract_ticket_ids([task])
                    if ticket_ids:
                        task_info["ticket_id"] = ticket_ids[0]
                        logger.debug(f"📄 Found queued task: {task_info['title']} (Ticket: {task_info['ticket_id']})")
                    else:
                        task_info["ticket_id"] = None
                        logger.warning(f"⚠️ Could not extract ticket ID for queued task: {task_info['title']}")
                    
                    processed_tasks.append(task_info)
                    
                except Exception as task_error:
                    logger.error(f"❌ Error processing individual queued task: {task_error}")
                    continue
            
            log_key_value(logger, "📊 Queued tasks detected", str(len(processed_tasks)))
            
            if processed_tasks:
                logger.info("✅ Found queued tasks ready for processing:")
                for task in processed_tasks:
                    ticket_display = task.get("ticket_id", "No ID")
                    logger.info(f"   🎯 {task['title']} (Ticket: {ticket_display})")
            else:
                logger.info("ℹ️  No tasks found with 'Queued to run' status")
            
            return processed_tasks
            
        except Exception as e:
            logger.error(f"❌ Failed to detect queued tasks: {e}")
            raise
    
    def has_queued_tasks(self) -> bool:
        """
        Check if there are any tickets with 'Queued to run' status.
        
        Returns:
            True if there are queued tasks, False otherwise
        """
        try:
            queued_tasks = self.get_queued_tasks()
            has_tasks = len(queued_tasks) > 0
            logger.info(f"🔍 Queued task check result: {'Tasks found' if has_tasks else 'No tasks found'}")
            return has_tasks
        except Exception as e:
            logger.error(f"❌ Failed to check for queued tasks: {e}")
            return False