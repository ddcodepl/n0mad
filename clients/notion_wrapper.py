import os
import asyncio
import aiohttp
import time
from typing import Optional, Dict, Any, List
from notion_client import Client
from utils.task_status import TaskStatus
from utils.logging_config import get_logger, log_section_header, log_subsection_header, log_key_value, log_list_items
from utils.global_config import get_global_config
from utils.env_security import mask_sensitive_dict

logger = get_logger(__name__)


class NotionClientWrapper:
    def __init__(self, token: Optional[str] = None, database_id: Optional[str] = None, max_retries: int = 3):
        """
        Initialize Notion client with secure credential management.
        
        Args:
            token: Notion token (if None, uses global config)
            database_id: Notion database ID (if None, uses global config)
            max_retries: Maximum retry attempts for API calls
        """
        # Use global configuration for secure credential management
        global_config = get_global_config(strict_validation=False)
        
        self.token = token or global_config.get("NOTION_TOKEN")
        if not self.token:
            raise ValueError(
                "Notion token not found. Set NOTION_TOKEN environment variable or configure it globally. "
                "Run 'nomad --config-help' for setup instructions."
            )
        
        self.database_id = database_id or global_config.get("NOTION_BOARD_DB")
        if not self.database_id:
            raise ValueError(
                "Notion database ID not found. Set NOTION_BOARD_DB environment variable or configure it globally. "
                "Run 'nomad --config-help' for setup instructions."
            )
        
        # Validate credentials using security manager
        security_manager = global_config.security_manager
        
        # Validate Notion token format
        if not security_manager.validate_notion_token(self.token):
            logger.warning("⚠️ Notion token format appears invalid. Expected format: secret_...")
        
        # Validate database ID format
        if not security_manager.validate_notion_database_id(self.database_id):
            logger.warning("⚠️ Notion database ID format appears invalid. Expected: 32-character hex string")
        
        self.max_retries = max_retries
        
        try:
            self.client = Client(auth=self.token)
            
            # Log success with masked credentials
            masked_token = security_manager.mask_sensitive_value(self.token)
            logger.info(f"✅ Notion client initialized successfully (token: {masked_token})")
            
        except Exception as e:
            # Ensure no sensitive data is logged in errors
            error_msg = str(e)
            if self.token in error_msg:
                error_msg = error_msg.replace(self.token, security_manager.mask_sensitive_value(self.token))
            
            logger.error(f"❌ Failed to initialize Notion client: {error_msg}")
            raise ValueError(f"Notion client initialization failed. Check your credentials. {error_msg}") from e
    
    def _retry_with_exponential_backoff(self, func, *args, **kwargs):
        """
        Retry a function with exponential backoff for handling rate limits and temporary failures.
        """
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                
                # Check if it's a rate limit error or temporary failure
                if "rate" in error_str or "429" in error_str or "timeout" in error_str or "connection" in error_str:
                    if attempt < self.max_retries - 1:
                        delay = (2 ** attempt) + (time.time() % 1)  # Exponential backoff with jitter
                        logger.warning(f"⚠️ API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                        logger.info(f"⏳ Retrying in {delay:.2f} seconds...")
                        time.sleep(delay)
                        continue
                
                # For non-retryable errors or final attempt, raise immediately
                logger.error(f"❌ API call failed after {attempt + 1} attempts: {e}")
                raise
        
        # This should never be reached, but just in case
        raise Exception(f"Failed after {self.max_retries} attempts")
    
    def test_connection(self) -> bool:
        try:
            database = self._retry_with_exponential_backoff(
                self.client.databases.retrieve,
                database_id=self.database_id
            )
            db_title = database.get('title', [{}])[0].get('plain_text', 'Untitled')
            logger.info(f"✅ Successfully connected to database: {db_title}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Notion database: {e}")
            return False
    
    def debug_database_schema(self) -> Dict[str, Any]:
        """
        Retrieve and analyze the database schema to understand property types.
        This helps debug filter issues by showing exact property names and types.
        """
        try:
            database = self.client.databases.retrieve(database_id=self.database_id)
            properties = database.get("properties", {})
            
            log_section_header(logger, "DATABASE SCHEMA DEBUG")
            
            db_title = database.get('title', [{}])[0].get('plain_text', 'Untitled')
            log_key_value(logger, "🆔 Database ID", self.database_id)
            log_key_value(logger, "📋 Database Title", db_title)
            log_key_value(logger, "🔢 Total Properties", str(len(properties)))
            
            log_subsection_header(logger, "Property Details")
            
            # Log all properties with their types
            for prop_name, prop_config in properties.items():
                prop_type = prop_config.get("type", "unknown")
                log_key_value(logger, f"📝 Property '{prop_name}'", f"Type: {prop_type}")
                
                # For select properties, show available options
                if prop_type == "select" and "select" in prop_config:
                    options = prop_config["select"].get("options", [])
                    option_details = []
                    for option in options:
                        option_name = option.get("name", "unnamed")
                        option_color = option.get("color", "no color")
                        option_details.append(f"'{option_name}' ({option_color})")
                    log_list_items(logger, "  📋 Select Options", option_details)
                
                # For multi-select properties, show available options
                elif prop_type == "multi_select" and "multi_select" in prop_config:
                    options = prop_config["multi_select"].get("options", [])
                    option_details = []
                    for option in options:
                        option_name = option.get("name", "unnamed")
                        option_color = option.get("color", "no color")
                        option_details.append(f"'{option_name}' ({option_color})")
                    log_list_items(logger, "  🏷️  Multi-Select Options", option_details)
                
                # For status properties, show available options
                elif prop_type == "status" and "status" in prop_config:
                    options = prop_config["status"].get("options", [])
                    option_details = []
                    for option in options:
                        option_name = option.get("name", "unnamed")
                        option_color = option.get("color", "no color")
                        option_details.append(f"'{option_name}' ({option_color})")
                    log_list_items(logger, "  📊 Status Options", option_details)
            
            # Specifically check for Status property
            if "Status" in properties:
                log_subsection_header(logger, "STATUS PROPERTY ANALYSIS")
                status_prop = properties["Status"]
                status_type = status_prop.get("type", "unknown")
                log_key_value(logger, "🎯 Status Property Type", status_type)
                
                # Suggest correct filter format based on property type
                if status_type == "select":
                    logger.info("✅ Correct filter format for SELECT type:")
                    logger.info('   {"property": "Status", "select": {"equals": "status_name"}}')
                elif status_type == "status":
                    logger.info("✅ Correct filter format for STATUS type:")
                    logger.info('   {"property": "Status", "status": {"equals": "status_name"}}')
                elif status_type == "multi_select":
                    logger.info("✅ Correct filter format for MULTI_SELECT type:")
                    logger.info('   {"property": "Status", "multi_select": {"contains": "status_name"}}')
                else:
                    logger.warning(f"⚠️  Unknown status property type: {status_type}")
                    logger.warning("Please check Notion API documentation for correct filter format")
            else:
                log_subsection_header(logger, "STATUS PROPERTY NOT FOUND")
                logger.error("❌ 'Status' property not found in database!")
                available_props = list(properties.keys())
                log_list_items(logger, "Available properties", available_props)
                logger.warning("⚠️  Note: Property names are case-sensitive!")
            
            log_section_header(logger, "END SCHEMA DEBUG")
            
            return database
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve database schema: {e}")
            raise
    
    def get_status_property_type(self) -> tuple[str, Dict[str, Any]]:
        """
        Get the Status property type and configuration.
        Returns tuple of (property_type, property_config)
        """
        try:
            database = self.client.databases.retrieve(database_id=self.database_id)
            properties = database.get("properties", {})
            
            if "Status" not in properties:
                available_props = list(properties.keys())
                raise ValueError(f"Status property not found. Available properties: {available_props}")
            
            status_prop = properties["Status"]
            prop_type = status_prop.get("type", "unknown")
            
            logger.info(f"🎯 Status property type detected: {prop_type}")
            return prop_type, status_prop
            
        except Exception as e:
            logger.error(f"❌ Failed to get Status property type: {e}")
            raise
    
    def create_status_filter(self, status_value: str) -> Dict[str, Any]:
        """
        Create the correct filter format for the Status property based on its type.
        """
        try:
            prop_type, prop_config = self.get_status_property_type()
            
            if prop_type == "select":
                filter_dict = {
                    "property": "Status",
                    "select": {
                        "equals": status_value
                    }
                }
            elif prop_type == "status":
                filter_dict = {
                    "property": "Status",
                    "status": {
                        "equals": status_value
                    }
                }
            elif prop_type == "multi_select":
                filter_dict = {
                    "property": "Status",
                    "multi_select": {
                        "contains": status_value
                    }
                }
            else:
                raise ValueError(f"Unsupported Status property type: {prop_type}")
            
            logger.info(f"✅ Created filter for status '{status_value}': {filter_dict}")
            return filter_dict
            
        except Exception as e:
            logger.error(f"❌ Failed to create status filter: {e}")
            raise
    
    def query_database(self, filter_dict: Optional[Dict[str, Any]] = None, start_cursor: Optional[str] = None, page_size: int = 100) -> Dict[str, Any]:
        try:
            query_params = {"database_id": self.database_id, "page_size": page_size}
            if filter_dict:
                query_params["filter"] = filter_dict
            if start_cursor:
                query_params["start_cursor"] = start_cursor
            
            response = self._retry_with_exponential_backoff(
                self.client.databases.query,
                **query_params
            )
            return response
        except Exception as e:
            logger.error(f"Failed to query database: {e}")
            raise
    
    def query_tickets_by_status(self, status: str, include_all_pages: bool = True) -> List[Dict[str, Any]]:
        """
        Query Notion database for tickets with a specific status.
        
        Args:
            status: The status to filter by (e.g., 'Prepare Tasks')
            include_all_pages: If True, fetch all pages with pagination
        
        Returns:
            List of page objects with their IDs and properties
        """
        try:
            logger.info(f"🔍 Querying tickets with status: '{status}'")
            
            # Create the status filter
            status_filter = self.create_status_filter(status)
            
            all_results = []
            start_cursor = None
            
            while True:
                # Query the database with pagination
                response = self.query_database(
                    filter_dict=status_filter,
                    start_cursor=start_cursor,
                    page_size=100
                )
                
                results = response.get("results", [])
                all_results.extend(results)
                
                logger.info(f"📄 Retrieved {len(results)} tickets in this batch")
                
                # Check if there are more pages
                has_more = response.get("has_more", False)
                next_cursor = response.get("next_cursor")
                
                if not include_all_pages or not has_more or not next_cursor:
                    break
                
                start_cursor = next_cursor
                logger.info(f"📄 Fetching next page (cursor: {start_cursor[:10]}...)")
            
            logger.info(f"✅ Total tickets found with status '{status}': {len(all_results)}")
            return all_results
            
        except Exception as e:
            logger.error(f"❌ Failed to query tickets by status '{status}': {e}")
            raise
    
    def extract_ticket_ids(self, pages: List[Dict[str, Any]]) -> List[str]:
        """
        Extract ticket IDs from Notion page properties.
        
        Args:
            pages: List of Notion page objects
        
        Returns:
            List of clean ticket IDs
        """
        ticket_ids = []
        
        for page in pages:
            try:
                page_id = page.get("id", "")
                properties = page.get("properties", {})
                
                # Try to extract ticket ID from different property types
                ticket_id = None
                
                # Method 1: Try 'ID' property (unique_id type)
                if "ID" in properties:
                    id_prop = properties["ID"]
                    if id_prop.get("type") == "unique_id" and id_prop.get("unique_id"):
                        unique_id = id_prop["unique_id"]
                        prefix = unique_id.get("prefix", "")
                        number = unique_id.get("number", "")
                        ticket_id = f"{prefix}-{number}" if prefix and number else str(number)
                        logger.debug(f"📝 Extracted ID from unique_id property: {ticket_id}")
                
                # Method 2: Try 'Name' property (title type) - look for patterns like NOMAD-12
                if not ticket_id and "Name" in properties:
                    name_prop = properties["Name"]
                    if name_prop.get("type") == "title" and name_prop.get("title"):
                        title_text = name_prop["title"][0]["plain_text"] if name_prop["title"] else ""
                        # Look for pattern like NOMAD-12, TICKET-123, etc.
                        import re
                        match = re.search(r'([A-Z]+-\d+)', title_text)
                        if match:
                            ticket_id = match.group(1)
                            logger.debug(f"📝 Extracted ID from title pattern: {ticket_id}")
                
                # Method 3: If no specific ID found, use a portion of the page ID
                if not ticket_id:
                    # Use last 8 characters of page ID as fallback
                    ticket_id = page_id.replace("-", "")[-8:] if page_id else None
                    logger.debug(f"📝 Using page ID fallback: {ticket_id}")
                
                if ticket_id:
                    ticket_ids.append(ticket_id)
                    logger.info(f"✅ Extracted ticket ID: {ticket_id} from page {page_id[:8]}...")
                else:
                    logger.warning(f"⚠️ Could not extract ticket ID from page {page_id[:8]}...")
                    
            except Exception as e:
                logger.error(f"❌ Failed to extract ticket ID from page {page.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"📊 Successfully extracted {len(ticket_ids)} ticket IDs from {len(pages)} pages")
        return ticket_ids
    
    def update_tickets_status_batch(self, page_ids: List[str], new_status: str) -> Dict[str, Any]:
        """
        Update status for multiple Notion pages in batch with individual error handling.
        
        Args:
            page_ids: List of Notion page IDs to update
            new_status: New status to set for all pages
        
        Returns:
            Dictionary with success/failure results
        """
        results = {
            "successful_updates": [],
            "failed_updates": [],
            "total_processed": len(page_ids),
            "success_count": 0,
            "failure_count": 0
        }
        
        logger.info(f"🔄 Starting batch status update for {len(page_ids)} pages to '{new_status}'")
        
        for i, page_id in enumerate(page_ids):
            try:
                logger.info(f"📄 Updating page {i+1}/{len(page_ids)}: {page_id[:8]}...")
                
                updated_page = self.update_page_status(page_id, new_status)
                
                results["successful_updates"].append({
                    "page_id": page_id,
                    "status": new_status,
                    "updated_at": updated_page.get("last_edited_time", "unknown")
                })
                results["success_count"] += 1
                
                logger.info(f"✅ Successfully updated page {page_id[:8]}... to '{new_status}'")
                
            except Exception as e:
                error_info = {
                    "page_id": page_id,
                    "error": str(e),
                    "attempted_status": new_status
                }
                results["failed_updates"].append(error_info)
                results["failure_count"] += 1
                
                logger.error(f"❌ Failed to update page {page_id[:8]}...: {e}")
                
                # Continue with next page instead of failing entire batch
                continue
        
        # Summary logging
        logger.info(f"📊 Batch update completed:")
        logger.info(f"   ✅ Successful updates: {results['success_count']}")
        logger.info(f"   ❌ Failed updates: {results['failure_count']}")
        
        if results['total_processed'] > 0:
            success_rate = (results['success_count']/results['total_processed']*100)
            logger.info(f"   📊 Success rate: {success_rate:.1f}%")
        else:
            logger.info(f"   📊 Success rate: N/A (no pages processed)")
        
        if results["failed_updates"]:
            logger.warning(f"⚠️ Failed page IDs: {[f['page_id'][:8] + '...' for f in results['failed_updates']]}")
        
        return results
    
    def upload_tasks_files_to_pages(self, ticket_data_with_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upload generated JSON task files to Notion page 'Tasks' property.
        
        Args:
            ticket_data_with_files: List of ticket data with file paths to upload
            
        Returns:
            Dictionary with upload results
        """
        results = {
            "successful_uploads": [],
            "failed_uploads": [],
            "total_processed": len(ticket_data_with_files),
            "success_count": 0,
            "failure_count": 0
        }
        
        logger.info(f"📤 Starting tasks file upload for {len(ticket_data_with_files)} tickets")
        
        for i, ticket_data in enumerate(ticket_data_with_files):
            try:
                ticket_id = ticket_data.get("ticket_id")
                page_id = ticket_data.get("page_id")
                file_path = ticket_data.get("tasks_file_path")
                
                if not all([ticket_id, page_id, file_path]):
                    raise ValueError(f"Missing required data: ticket_id={ticket_id}, page_id={page_id}, file_path={file_path}")
                
                logger.info(f"📤 Uploading tasks file for ticket {i+1}/{len(ticket_data_with_files)}: {ticket_id}")
                
                # Upload file to Notion page
                upload_result = self._upload_file_to_page_property(page_id, file_path, "Tasks")
                
                results["successful_uploads"].append({
                    "ticket_id": ticket_id,
                    "page_id": page_id,
                    "file_path": file_path,
                    "upload_result": upload_result,
                    "uploaded_at": upload_result.get("uploaded_at")
                })
                results["success_count"] += 1
                
                logger.info(f"✅ Successfully uploaded tasks file for ticket {ticket_id}")
                
            except Exception as e:
                error_info = {
                    "ticket_id": ticket_data.get("ticket_id", "unknown"),
                    "page_id": ticket_data.get("page_id", "unknown"), 
                    "file_path": ticket_data.get("tasks_file_path", "unknown"),
                    "error": str(e)
                }
                results["failed_uploads"].append(error_info)
                results["failure_count"] += 1
                
                logger.error(f"❌ Failed to upload tasks file for ticket {ticket_data.get('ticket_id', 'unknown')}: {e}")
                continue
        
        # Summary logging
        logger.info(f"📊 Tasks file upload completed:")
        logger.info(f"   ✅ Successful uploads: {results['success_count']}")
        logger.info(f"   ❌ Failed uploads: {results['failure_count']}")
        
        if results['total_processed'] > 0:
            success_rate = (results['success_count']/results['total_processed']*100)
            logger.info(f"   📊 Success rate: {success_rate:.1f}%")
        else:
            logger.info(f"   📊 Success rate: N/A (no files processed)")
        
        if results["failed_uploads"]:
            failed_ids = [f["ticket_id"] for f in results["failed_uploads"]]
            logger.warning(f"⚠️ Failed ticket IDs: {failed_ids}")
        
        return results
    
    def _upload_file_to_page_property(self, page_id: str, file_path: str, property_name: str = "Tasks") -> Dict[str, Any]:
        """
        Upload a file to a Notion page property (like 'Tasks' property).
        
        Args:
            page_id: Notion page ID
            file_path: Local file path to upload
            property_name: Name of the property to upload to
            
        Returns:
            Dictionary with upload result information
        """
        import os
        from pathlib import Path
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        logger.info(f"📁 Uploading file: {file_name} ({file_size} bytes) to property '{property_name}'")
        
        try:
            # Read file content
            with open(file_path, 'rb') as file:
                file_content = file.read()
            
            # Notion API doesn't directly support file uploads to properties via API
            # We need to use a workaround: create a file block and then reference it
            # Or use external file hosting and store the URL
            
            # For now, let's implement a workaround by updating the page with file information
            # In a production system, you'd typically upload to a file storage service first
            
            # First, clear any existing files in the Tasks property
            clear_property = {
                property_name: {
                    "files": []
                }
            }
            
            # Clear existing files first
            self._retry_with_exponential_backoff(
                self.client.pages.update,
                page_id=page_id,
                properties=clear_property
            )
            
            logger.info(f"🧹 Cleared existing files from property '{property_name}'")
            
            # Create file reference in the Tasks property
            # Since Tasks is a 'files' property type, we need to format it correctly
            file_property = {
                property_name: {
                    "files": [
                        {
                            "name": file_name,
                            "type": "external",
                            "external": {
                                "url": f"file://localhost/{os.path.abspath(file_path)}"  # Local file reference
                            }
                        }
                    ]
                }
            }
            
            # Update the page with file property
            updated_page = self._retry_with_exponential_backoff(
                self.client.pages.update,
                page_id=page_id,
                properties=file_property
            )
            
            upload_result = {
                "file_name": file_name,
                "file_size": file_size,
                "property_name": property_name,
                "page_id": page_id,
                "uploaded_at": updated_page.get("last_edited_time"),
                "local_path": os.path.abspath(file_path)
            }
            
            logger.info(f"✅ File reference added to page {page_id[:8]}... property '{property_name}'")
            return upload_result
            
        except Exception as e:
            logger.error(f"❌ Failed to upload file to page property: {e}")
            raise
    
    def finalize_ticket_status(self, successful_ticket_data: List[Dict[str, Any]], final_status: str = "Ready to run") -> Dict[str, Any]:
        """
        Update processed tickets to final status ('Ready to run') after successful completion.
        
        Args:
            successful_ticket_data: List of successfully processed ticket data with page_ids
            final_status: Final status to set (default: 'Ready to run')
        
        Returns:
            Dictionary with finalization results and rollback information
        """
        results = {
            "finalized_tickets": [],
            "failed_finalizations": [],
            "rollback_attempted": [],
            "rollback_successful": [],
            "rollback_failed": [],
            "total_processed": len(successful_ticket_data),
            "success_count": 0,
            "failure_count": 0,
            "summary": {}
        }
        
        logger.info(f"🏁 Starting final status update for {len(successful_ticket_data)} tickets")
        logger.info(f"🎯 Target final status: '{final_status}'")
        
        # Extract page IDs from successful ticket data
        page_ids = []
        page_id_to_ticket = {}
        
        for ticket_data in successful_ticket_data:
            page_id = ticket_data.get("page_id")
            ticket_id = ticket_data.get("ticket_id")
            
            if page_id and ticket_id:
                page_ids.append(page_id)
                page_id_to_ticket[page_id] = ticket_data
            else:
                logger.warning(f"⚠️ Skipping ticket data with missing page_id or ticket_id: {ticket_data}")
        
        logger.info(f"📄 Extracted {len(page_ids)} valid page IDs for finalization")
        
        if not page_ids:
            logger.warning("⚠️ No valid page IDs found for finalization")
            results["summary"] = {
                "message": "No valid tickets to finalize",
                "total_attempted": 0,
                "successful_finalizations": 0,
                "failed_finalizations": 0,
                "rollback_needed": False
            }
            return results
        
        # Attempt to update all tickets to final status
        finalization_results = self.update_tickets_status_batch(page_ids, final_status)
        
        # Process results and handle rollbacks if needed
        for success_item in finalization_results["successful_updates"]:
            page_id = success_item["page_id"]
            ticket_data = page_id_to_ticket[page_id]
            
            results["finalized_tickets"].append({
                "ticket_id": ticket_data["ticket_id"],
                "page_id": page_id,
                "final_status": final_status,
                "updated_at": success_item.get("updated_at"),
                "original_data": ticket_data
            })
            results["success_count"] += 1
            
            logger.info(f"✅ Finalized ticket {ticket_data['ticket_id']} to '{final_status}'")
        
        # Handle failed finalizations
        for failure_item in finalization_results["failed_updates"]:
            page_id = failure_item["page_id"]
            ticket_data = page_id_to_ticket[page_id]
            
            results["failed_finalizations"].append({
                "ticket_id": ticket_data["ticket_id"],
                "page_id": page_id,
                "error": failure_item["error"],
                "original_data": ticket_data
            })
            results["failure_count"] += 1
            
            logger.error(f"❌ Failed to finalize ticket {ticket_data['ticket_id']}: {failure_item['error']}")
        
        # Determine if rollback is needed
        rollback_needed = results["failure_count"] > 0 and results["success_count"] > 0
        
        if rollback_needed:
            logger.warning(f"⚠️ Partial failure detected. Attempting rollback for {results['success_count']} successful updates...")
            rollback_results = self._attempt_rollback(results["finalized_tickets"])
            results.update(rollback_results)
        
        # Generate comprehensive summary
        results["summary"] = {
            "message": f"Finalization completed with {results['success_count']} successes and {results['failure_count']} failures",
            "total_attempted": results["total_processed"],
            "successful_finalizations": results["success_count"],
            "failed_finalizations": results["failure_count"], 
            "rollback_needed": rollback_needed,
            "rollback_attempted": len(results["rollback_attempted"]),
            "rollback_successful": len(results["rollback_successful"]),
            "rollback_failed": len(results["rollback_failed"]),
            "final_status": final_status
        }
        
        # Final summary logging
        logger.info(f"📊 Finalization Summary:")
        logger.info(f"   🎯 Target Status: '{final_status}'")
        logger.info(f"   ✅ Successfully finalized: {results['success_count']}")
        logger.info(f"   ❌ Failed to finalize: {results['failure_count']}")
        
        if rollback_needed:
            logger.info(f"   🔄 Rollback attempted: {len(results['rollback_attempted'])}")
            logger.info(f"   ✅ Rollback successful: {len(results['rollback_successful'])}")
            logger.info(f"   ❌ Rollback failed: {len(results['rollback_failed'])}")
        
        if results['total_processed'] > 0:
            success_rate = (results['success_count']/results['total_processed']*100)
            logger.info(f"   📊 Success rate: {success_rate:.1f}%")
        
        return results
    
    def _attempt_rollback(self, finalized_tickets: List[Dict[str, Any]], rollback_status: str = "Preparing Tasks") -> Dict[str, List]:
        """
        Attempt to rollback successfully finalized tickets to previous status.
        
        Args:
            finalized_tickets: List of successfully finalized tickets
            rollback_status: Status to rollback to (default: 'Preparing Tasks')
        
        Returns:
            Dictionary with rollback results
        """
        rollback_results = {
            "rollback_attempted": [],
            "rollback_successful": [],
            "rollback_failed": []
        }
        
        logger.info(f"🔄 Starting rollback to '{rollback_status}' for {len(finalized_tickets)} tickets")
        
        for ticket_info in finalized_tickets:
            page_id = ticket_info["page_id"]
            ticket_id = ticket_info["ticket_id"]
            
            try:
                logger.info(f"🔄 Rolling back ticket {ticket_id}...")
                
                rollback_results["rollback_attempted"].append(ticket_info)
                
                # Attempt rollback
                self.update_page_status(page_id, rollback_status)
                
                rollback_results["rollback_successful"].append({
                    **ticket_info,
                    "rollback_status": rollback_status
                })
                
                logger.info(f"✅ Successfully rolled back ticket {ticket_id} to '{rollback_status}'")
                
            except Exception as e:
                rollback_results["rollback_failed"].append({
                    **ticket_info,
                    "rollback_error": str(e)
                })
                
                logger.error(f"❌ Failed to rollback ticket {ticket_id}: {e}")
                continue
        
        return rollback_results
    
    def get_page(self, page_id: str) -> Dict[str, Any]:
        try:
            page = self.client.pages.retrieve(page_id=page_id)
            return page
        except Exception as e:
            logger.error(f"Failed to retrieve page {page_id}: {e}")
            raise
    
    def update_page(self, page_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        try:
            updated_page = self._retry_with_exponential_backoff(
                self.client.pages.update,
                page_id=page_id,
                properties=properties
            )
            logger.info(f"Successfully updated page {page_id}")
            return updated_page
        except Exception as e:
            logger.error(f"Failed to update page {page_id}: {e}")
            raise
    
    def update_page_status(self, page_id: str, status: str) -> Dict[str, Any]:
        """
        Update a page's status property using the correct format based on property type.
        This is a robust helper method that automatically detects the correct format.
        """
        try:
            prop_type, _ = self.get_status_property_type()
            
            if prop_type == "select":
                properties = {
                    "Status": {
                        "select": {
                            "name": status
                        }
                    }
                }
            elif prop_type == "status":
                properties = {
                    "Status": {
                        "status": {
                            "name": status
                        }
                    }
                }
            elif prop_type == "multi_select":
                # For multi-select, we'll set it as a single option
                properties = {
                    "Status": {
                        "multi_select": [
                            {
                                "name": status
                            }
                        ]
                    }
                }
            else:
                logger.warning(f"Unknown status property type {prop_type}, using status format as default")
                properties = {
                    "Status": {
                        "status": {
                            "name": status
                        }
                    }
                }
            
            updated_page = self.update_page(page_id, properties)
            logger.info(f"Successfully updated page {page_id} status to '{status}' using {prop_type} format")
            return updated_page
            
        except Exception as e:
            logger.error(f"Failed to update page {page_id} status to '{status}': {e}")
            # Fallback to status format (which is more common now)
            try:
                properties = {
                    "Status": {
                        "status": {
                            "name": status
                        }
                    }
                }
                updated_page = self.update_page(page_id, properties)
                logger.info(f"Successfully updated page {page_id} status to '{status}' using fallback status format")
                return updated_page
            except Exception as fallback_error:
                logger.error(f"Fallback status update also failed: {fallback_error}")
                raise
    
    def update_page_property(self, page_id: str, property_name: str, property_value: str) -> Dict[str, Any]:
        """
        Update a specific page property with the given value.
        
        Args:
            page_id: Notion page ID
            property_name: Name of the property to update  
            property_value: New value for the property
            
        Returns:
            Updated page object
        """
        try:
            logger.info(f"🔄 Updating property '{property_name}' for page {page_id[:8]}...")
            
            # For now, assume it's a rich_text property (like Feedback)
            # This could be extended to handle other property types based on database schema
            properties = {
                property_name: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": property_value
                            }
                        }
                    ]
                }
            }
            
            updated_page = self.update_page(page_id, properties)
            logger.info(f"✅ Successfully updated property '{property_name}' for page {page_id[:8]}...")
            return updated_page
            
        except Exception as e:
            logger.error(f"❌ Failed to update property '{property_name}' for page {page_id}: {e}")
            raise
    
    def get_page_content(self, page_id: str) -> str:
        try:
            blocks = self.client.blocks.children.list(block_id=page_id)
            content_parts = []
            
            for block in blocks["results"]:
                block_type = block["type"]
                if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
                    text_content = self._extract_text_from_block(block)
                    if text_content:
                        content_parts.append(text_content)
            
            return "\n\n".join(content_parts)
        except Exception as e:
            logger.error(f"Failed to get page content for {page_id}: {e}")
            raise
    
    def _extract_text_from_block(self, block: Dict[str, Any]) -> str:
        block_type = block["type"]
        text_parts = []
        
        if block_type in block and "rich_text" in block[block_type]:
            for text_obj in block[block_type]["rich_text"]:
                if "text" in text_obj:
                    text_parts.append(text_obj["text"]["content"])
        
        return "".join(text_parts)
    
    def _extract_status_from_page(self, page: Dict[str, Any]) -> str:
        """
        Extract current status from a Notion page object.
        
        Args:
            page: Notion page object
            
        Returns:
            Current status string
        """
        try:
            properties = page.get("properties", {})
            status_prop = properties.get("Status", {})
            
            # Handle different status property types
            if "status" in status_prop and status_prop["status"]:
                return status_prop["status"]["name"]
            elif "select" in status_prop and status_prop["select"]:
                return status_prop["select"]["name"]
            else:
                logger.warning("⚠️ Could not extract status from page properties")
                return "Unknown"
                
        except Exception as e:
            logger.error(f"❌ Error extracting status from page: {e}")
            return "Unknown"
    
    async def _delete_blocks_async(self, block_ids: List[str], headers: Dict[str, str], shutdown_flag: callable = None):
        """Asynchronously delete multiple blocks concurrently with rate limiting"""
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=10)  # Limit concurrent connections
        ) as session:
            
            # Create semaphore to limit concurrent requests (Notion API allows ~3 req/sec)
            semaphore = asyncio.Semaphore(5)  # Allow up to 5 concurrent deletions
            
            async def delete_block(block_id: str):
                # Check for shutdown before processing each block
                if shutdown_flag and shutdown_flag():
                    logger.debug(f"⏹️  Shutdown requested, skipping deletion of block {block_id}")
                    return {"block_id": block_id, "success": False, "error": "Shutdown requested"}
                
                async with semaphore:
                    url = f"https://api.notion.com/v1/blocks/{block_id}"
                    try:
                        async with session.delete(url, headers=headers) as response:
                            if response.status == 200:
                                logger.debug(f"✅ Deleted block {block_id}")
                                return {"block_id": block_id, "success": True}
                            elif response.status == 429:  # Rate limited
                                # Wait and retry once
                                await asyncio.sleep(1)
                                async with session.delete(url, headers=headers) as retry_response:
                                    if retry_response.status == 200:
                                        logger.debug(f"✅ Deleted block {block_id} (after retry)")
                                        return {"block_id": block_id, "success": True}
                                    else:
                                        logger.error(f"❌ Failed to delete block {block_id} after retry: {retry_response.status}")
                                        return {"block_id": block_id, "success": False, "error": f"HTTP {retry_response.status}"}
                            elif response.status == 409:  # Conflict - block might be locked/processing
                                # Wait longer and retry once for conflict resolution  
                                logger.warning(f"⚠️  Block {block_id} conflict (409), waiting and retrying...")
                                await asyncio.sleep(2)
                                async with session.delete(url, headers=headers) as retry_response:
                                    if retry_response.status == 200:
                                        logger.debug(f"✅ Deleted block {block_id} (after conflict retry)")
                                        return {"block_id": block_id, "success": True}
                                    elif retry_response.status == 409:
                                        # Still conflicted - this block might have dependencies, skip it
                                        logger.warning(f"⚠️  Block {block_id} still conflicted after retry, skipping (may have dependencies)")
                                        return {"block_id": block_id, "success": False, "error": "HTTP 409 - Conflict (dependencies)"}
                                    else:
                                        logger.error(f"❌ Failed to delete block {block_id} after conflict retry: {retry_response.status}")
                                        return {"block_id": block_id, "success": False, "error": f"HTTP {retry_response.status}"}
                            elif response.status == 404:  # Block already deleted
                                logger.debug(f"✅ Block {block_id} already deleted (404)")
                                return {"block_id": block_id, "success": True}
                            else:
                                logger.error(f"❌ Failed to delete block {block_id}: HTTP {response.status}")
                                return {"block_id": block_id, "success": False, "error": f"HTTP {response.status}"}
                    except Exception as e:
                        logger.error(f"❌ Exception deleting block {block_id}: {e}")
                        return {"block_id": block_id, "success": False, "error": str(e)}
            
            # Execute all deletions concurrently
            delete_tasks = [delete_block(block_id) for block_id in block_ids]
            results = await asyncio.gather(*delete_tasks)
            
            # Count successes and failures
            successful_deletions = sum(1 for result in results if result.get("success"))
            failed_deletions = len(results) - successful_deletions
            
            logger.info(f"🗑️  Block deletion results: {successful_deletions} successful, {failed_deletions} failed")
            
            if failed_deletions > 0:
                failed_blocks = [result["block_id"] for result in results if not result.get("success")]
                conflict_blocks = [result["block_id"] for result in results if not result.get("success") and "409" in str(result.get("error", ""))]
                
                if conflict_blocks:
                    logger.warning(f"⚠️  {len(conflict_blocks)} blocks had conflicts (409) - likely have dependencies or are being processed")
                if len(failed_blocks) > len(conflict_blocks):
                    other_failed = len(failed_blocks) - len(conflict_blocks)
                    logger.warning(f"⚠️  {other_failed} blocks failed for other reasons")
                
                logger.info(f"📝 Continuing with content creation despite {failed_deletions} deletion failures...")
            
            return results

    async def _create_blocks_async(self, page_id: str, blocks: List[Dict], headers: Dict[str, str], shutdown_flag: callable = None):
        """Asynchronously create multiple blocks concurrently with rate limiting"""
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=5)  # Limit concurrent connections
        ) as session:
            
            # Split blocks into chunks of 100 (Notion API limit)
            chunk_size = 100
            block_chunks = [blocks[i:i + chunk_size] for i in range(0, len(blocks), chunk_size)]
            
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(3)  # Allow up to 3 concurrent create operations
            
            async def create_chunk(chunk_index: int, chunk: List[Dict]):
                # Check for shutdown before processing each chunk
                if shutdown_flag and shutdown_flag():
                    logger.debug(f"⏹️  Shutdown requested, skipping creation of chunk {chunk_index + 1}")
                    return {"chunk_index": chunk_index, "success": False, "error": "Shutdown requested"}
                
                async with semaphore:
                    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
                    payload = {"children": chunk}
                    
                    try:
                        async with session.patch(url, headers=headers, json=payload) as response:
                            if response.status == 200:
                                logger.debug(f"✅ Created block chunk {chunk_index + 1}/{len(block_chunks)} with {len(chunk)} blocks")
                                return {"chunk_index": chunk_index, "success": True, "block_count": len(chunk)}
                            elif response.status == 429:  # Rate limited
                                # Wait and retry once
                                await asyncio.sleep(2)
                                async with session.patch(url, headers=headers, json=payload) as retry_response:
                                    if retry_response.status == 200:
                                        logger.debug(f"✅ Created block chunk {chunk_index + 1}/{len(block_chunks)} (after retry)")
                                        return {"chunk_index": chunk_index, "success": True, "block_count": len(chunk)}
                                    else:
                                        logger.error(f"❌ Failed to create chunk {chunk_index + 1} after retry: {retry_response.status}")
                                        return {"chunk_index": chunk_index, "success": False, "error": f"HTTP {retry_response.status}"}
                            else:
                                error_text = await response.text()
                                logger.error(f"❌ Failed to create block chunk {chunk_index + 1}: HTTP {response.status} - {error_text}")
                                return {"chunk_index": chunk_index, "success": False, "error": f"HTTP {response.status}"}
                    except Exception as e:
                        logger.error(f"❌ Exception creating block chunk {chunk_index + 1}: {e}")
                        return {"chunk_index": chunk_index, "success": False, "error": str(e)}
            
            # Execute all chunk creations concurrently
            create_tasks = [create_chunk(i, chunk) for i, chunk in enumerate(block_chunks)]
            results = await asyncio.gather(*create_tasks)
            
            # Count successes and failures
            successful_chunks = sum(1 for result in results if result.get("success"))
            failed_chunks = len(results) - successful_chunks
            total_blocks_created = sum(result.get("block_count", 0) for result in results if result.get("success"))
            
            logger.info(f"📝 Block creation results: {successful_chunks}/{len(block_chunks)} chunks successful, {total_blocks_created} total blocks created")
            
            if failed_chunks > 0:
                failed_chunk_indices = [result["chunk_index"] + 1 for result in results if not result.get("success")]
                logger.error(f"❌ Failed to create chunks: {failed_chunk_indices}")
                
                # Check if failures are due to shutdown
                shutdown_failures = [result for result in results if not result.get("success") and "Shutdown" in str(result.get("error", ""))]
                if shutdown_failures:
                    logger.info(f"⏹️  {len(shutdown_failures)} chunks failed due to shutdown - this is expected")
                    return results  # Don't raise exception for shutdown-related failures
                
                # For other failures, raise exception since this breaks content integrity
                logger.error(f"🚫 Content creation failed due to {failed_chunks} chunk failures")
                raise Exception(f"Failed to create {failed_chunks} block chunks. Content may be incomplete.")
            
            return results

    def _build_deletion_strategy(self, blocks_data: List[Dict]) -> Dict[str, List[str]]:
        """
        Build a hierarchical deletion strategy that handles block dependencies.
        Returns dict with 'leaf_blocks', 'parent_blocks', and 'all_blocks' lists.
        """
        all_block_ids = []
        blocks_with_children = []
        leaf_blocks = []
        
        for block in blocks_data:
            block_id = block["id"]
            all_block_ids.append(block_id)
            
            # Check if block has children (indicates it's a parent)
            has_children = block.get("has_children", False)
            block_type = block.get("type", "")
            
            # Some block types commonly have children
            parent_block_types = [
                "toggle", "bulleted_list_item", "numbered_list_item", 
                "to_do", "quote", "callout", "column_list", "table"
            ]
            
            if has_children or block_type in parent_block_types:
                blocks_with_children.append(block_id)
                logger.debug(f"📁 Block {block_id} identified as parent ({block_type}, has_children: {has_children})")
            else:
                leaf_blocks.append(block_id)
                logger.debug(f"📄 Block {block_id} identified as leaf ({block_type})")
        
        strategy = {
            "leaf_blocks": leaf_blocks,        # Delete these first (no dependencies)
            "parent_blocks": blocks_with_children,  # Delete these second (might have children)
            "all_blocks": all_block_ids       # All blocks for fallback
        }
        
        logger.info(f"🗂️  Deletion strategy: {len(leaf_blocks)} leaf blocks, {len(blocks_with_children)} parent blocks")
        return strategy

    async def _delete_blocks_hierarchical(self, deletion_strategy: Dict[str, List[str]], headers: Dict[str, str], shutdown_flag: callable = None):
        """
        Delete blocks in hierarchical order: leaf blocks first, then parent blocks.
        This reduces 409 conflicts by handling dependencies properly.
        """
        leaf_blocks = deletion_strategy["leaf_blocks"]
        parent_blocks = deletion_strategy["parent_blocks"]
        
        all_results = []
        
        # Step 1: Delete leaf blocks first (no dependencies)
        if leaf_blocks:
            logger.info(f"🌿 Step 1: Deleting {len(leaf_blocks)} leaf blocks...")
            leaf_results = await self._delete_blocks_async(leaf_blocks, headers, shutdown_flag)
            all_results.extend(leaf_results)
            
            # Small delay to let Notion process the deletions
            await asyncio.sleep(0.5)
        
        # Step 2: Delete parent blocks (dependencies should be resolved)
        if parent_blocks:
            logger.info(f"📁 Step 2: Deleting {len(parent_blocks)} parent blocks...")
            parent_results = await self._delete_blocks_async(parent_blocks, headers, shutdown_flag)
            all_results.extend(parent_results)
        
        # Summary
        total_successful = sum(1 for result in all_results if result.get("success"))
        total_failed = len(all_results) - total_successful
        
        logger.info(f"🗑️  Hierarchical deletion complete: {total_successful}/{len(all_results)} successful")
        
        return all_results

    def update_page_content(self, page_id: str, content: str, status: str = None, shutdown_flag: callable = None):
        try:
            # Check for shutdown before starting expensive operations
            if shutdown_flag and shutdown_flag():
                logger.info(f"Shutdown requested, aborting page content update for {page_id}")
                return
            
            # Get existing blocks with hierarchy information
            existing_blocks = self.client.blocks.children.list(block_id=page_id)
            blocks_data = existing_blocks["results"]
            
            # Build hierarchical deletion strategy
            deletion_strategy = self._build_deletion_strategy(blocks_data)
            
            # Delete existing blocks using hierarchical strategy
            if deletion_strategy["all_blocks"]:
                # Check for shutdown before expensive deletion operation
                if shutdown_flag and shutdown_flag():
                    logger.info(f"Shutdown requested, aborting block deletion for {page_id}")
                    return
                
                total_blocks = len(deletion_strategy["all_blocks"])
                logger.info(f"🗑️  Deleting {total_blocks} existing blocks using hierarchical strategy...")
                
                # Prepare headers for async requests
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                }
                
                # Delete blocks hierarchically (leaf blocks first, then parents)
                deletion_results = asyncio.run(self._delete_blocks_hierarchical(deletion_strategy, headers, shutdown_flag))
                
                # Check deletion results and adjust wait time based on conflicts
                conflict_count = sum(1 for result in deletion_results if not result.get("success") and "409" in str(result.get("error", "")))
                success_count = sum(1 for result in deletion_results if result.get("success"))
                
                logger.info(f"✅ Hierarchical deletion completed: {success_count}/{total_blocks} blocks deleted successfully")
                
                # Wait for deletions to complete on Notion's side
                if conflict_count > 0:
                    logger.info(f"⏳ Found {conflict_count} remaining conflicts, waiting for resolution...")
                    time.sleep(2)  # Shorter wait since hierarchical approach should reduce conflicts
                else:
                    logger.info("⏳ Waiting for block deletions to process on Notion's servers...")
                    time.sleep(1)  # Standard wait time
            
            # Prepare new blocks
            content_paragraphs = content.strip().split('\n\n')
            new_blocks = []
            
            for paragraph in content_paragraphs:
                if paragraph.strip():
                    if paragraph.startswith('# '):
                        new_blocks.append({
                            "type": "heading_1",
                            "heading_1": {
                                "rich_text": [{"type": "text", "text": {"content": paragraph[2:]}}]
                            }
                        })
                    elif paragraph.startswith('## '):
                        new_blocks.append({
                            "type": "heading_2",
                            "heading_2": {
                                "rich_text": [{"type": "text", "text": {"content": paragraph[3:]}}]
                            }
                        })
                    elif paragraph.startswith('### '):
                        new_blocks.append({
                            "type": "heading_3",
                            "heading_3": {
                                "rich_text": [{"type": "text", "text": {"content": paragraph[4:]}}]
                            }
                        })
                    elif paragraph.startswith('- '):
                        new_blocks.append({
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [{"type": "text", "text": {"content": paragraph[2:]}}]
                            }
                        })
                    else:
                        new_blocks.append({
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": paragraph}}]
                            }
                        })
            
            # Create new blocks using optimized async method but wait for completion
            if new_blocks:
                # Check for shutdown before expensive creation operation
                if shutdown_flag and shutdown_flag():
                    logger.info(f"Shutdown requested, aborting block creation for {page_id}")
                    return
                
                logger.info(f"Creating {len(new_blocks)} new blocks concurrently...")
                asyncio.run(self._create_blocks_async(page_id, new_blocks, headers, shutdown_flag))
                logger.info(f"Successfully created all {len(new_blocks)} new blocks concurrently")
            
            # Update status if provided
            if status:
                self.update_page_status(page_id, status)
            
            logger.info(f"Successfully replaced all content for page {page_id} with {len(new_blocks)} new blocks")
            
        except Exception as e:
            logger.error(f"Failed to update page content for {page_id}: {e}")
            raise