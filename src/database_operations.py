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