#!/usr/bin/env python3
"""
Combined main application for Notion API integration
Supports two modes:
1. --refine: Process tasks with 'To Refine' status (original main.py functionality)
2. --prepare: Process tasks with 'Prepare Tasks' status (original main_workflow.py functionality)

Global installation support - can be run from any directory.
"""
import os
import sys
import time
import signal
import logging
import argparse
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add project root to Python path to enable imports when running locally
# For global installation, the package structure is already in sys.path
if __name__ == "__main__":
    # Only add path adjustment when running as script (not when globally installed)
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Initialize global configuration first
from utils.global_config import initialize_global_config, get_global_config

# Initialize global configuration for the working directory
# Use non-strict validation during import to allow configuration commands to work
try:
    global_config = initialize_global_config(strict_validation=False)
except ValueError as e:
    print(f"Configuration error: {e}", file=sys.stderr)
    print("Run 'nomad --config-help' for configuration assistance.", file=sys.stderr)
    if __name__ == "__main__":
        sys.exit(1)
    else:
        raise

from clients.notion_wrapper import NotionClientWrapper
from clients.openai_client import OpenAIClient
from core.operations.database_operations import DatabaseOperations
from core.processors.content_processor import ContentProcessor
from utils.file_operations import FileOperations
from core.operations.command_executor import CommandExecutor
from core.managers.status_transition_manager import StatusTransitionManager
from core.managers.feedback_manager import FeedbackManager, ProcessingStage
from clients.claude_engine_invoker import ClaudeEngineInvoker, InvocationResult
from core.managers.task_file_manager import TaskFileManager, CopyResult
from core.processors.multi_queue_processor import MultiQueueProcessor
from utils.polling_scheduler import PollingScheduler, CircuitBreakerConfig
from utils.performance_integration import (
    initialize_performance_monitoring, 
    integrate_all_components,
    log_performance_summary,
    PerformanceContext
)
from utils.logging_config import get_logger
from utils.file_operations import get_tasks_dir
from utils.config import config_manager
from core.processors.simple_queued_processor import SimpleQueuedProcessor
from core.processors.multi_status_processor import MultiStatusProcessor

# Initialize enhanced logging with session files
from utils.logging_config import setup_logging
setup_logging(
    level=logging.INFO,
    enable_file_logging=True,
    use_colors=True
)

logger = logging.getLogger(__name__)


class NotionDeveloper:
    def __init__(self, mode="refine"):
        self.mode = mode
        self.running = True
        
        # Use global configuration for settings
        self.global_config = get_global_config()
        self.max_concurrent_tasks = int(self.global_config.get("NOMAD_MAX_CONCURRENT_TASKS", "3"))
        
        self.stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "start_time": datetime.now(),
            "last_poll": None
        }
        
        try:
            logger.info(f"Initializing Notion Developer application in {mode} mode...")
            
            # Initialize strict configuration for application execution
            # Also validate that critical environment variables are set
            self.global_config = initialize_global_config(strict_validation=True)
            
            # Additional validation for required variables
            self._validate_required_environment_variables()
            
            logger.info(f"Global config home: {self.global_config.get_home_directory()}")
            logger.info(f"Tasks directory: {self.global_config.get_tasks_directory()}")
            
            # For global installation, use current working directory as project root
            # unless we're in development mode
            if self._is_development_mode():
                self.project_root = os.path.dirname(os.path.dirname(__file__))
                logger.info(f"Development mode - using project root: {self.project_root}")
            else:
                # Always use the current working directory for global mode
                # This ensures task-master commands run in the user's project directory
                self.project_root = str(Path.cwd())
                logger.info(f"Global mode - using working directory: {self.project_root}")
                
                # Verify that TASKS_DIR is accessible from the working directory
                tasks_dir = self.global_config.get('TASKS_DIR')
                if tasks_dir:
                    abs_tasks_dir = Path(tasks_dir) if Path(tasks_dir).is_absolute() else Path(self.project_root) / tasks_dir
                    logger.info(f"Using TASKS_DIR: {tasks_dir} (resolved to: {abs_tasks_dir})")
            
            # Initialize performance monitoring
            logger.info("📊 Initializing performance monitoring...")
            initialize_performance_monitoring(
                collection_interval=2.0,  # Collect metrics every 2 seconds
                history_size=500,         # Keep 500 metrics in history
                enable_auto_gc=True,      # Enable automatic garbage collection
                auto_start=True           # Start monitoring immediately
            )
            integrate_all_components()    # Integrate with all components
            
            self.notion_client = NotionClientWrapper()
            self.openai_client = OpenAIClient()
            
            if mode == "refine":
                # Use consistent project root approach for refine mode
                self.file_ops = FileOperations()  # Will use TASKS_DIR from environment or default to ./tasks
                self.db_ops = DatabaseOperations(self.notion_client)
                self.processor = ContentProcessor(self.notion_client, self.openai_client, self.file_ops)
            elif mode == "prepare":
                # Initialize both FileOperations and CommandExecutor with the same project root context
                self.file_ops = FileOperations()  # Will use TASKS_DIR from environment or default to ./tasks
                # For prepare mode, ensure CommandExecutor uses the correct working directory
                self.cmd_executor = CommandExecutor(base_dir=None)  # Let it use cwd automatically
            elif mode == "queued":
                # Initialize simple queued processor
                self.simple_processor = SimpleQueuedProcessor(self.project_root)
            elif mode == "multi":
                # Initialize multi-status processor
                self.multi_processor = MultiStatusProcessor(self.project_root)
            
            if not self.notion_client.test_connection():
                raise Exception("Failed to connect to Notion database")
            
            logger.info("Application initialized successfully")
            logger.info(f"Configured for {self.max_concurrent_tasks} concurrent task processing")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            sys.exit(1)
    
    def _is_development_mode(self) -> bool:
        """Check if we're running in development mode (not globally installed)."""
        try:
            # Check if we're running from a local development directory
            current_file = Path(__file__).resolve()
            
            # Look for development indicators
            parent_dirs = current_file.parents
            for parent in parent_dirs:
                # Check for common development indicators
                dev_indicators = [
                    parent / 'pyproject.toml',
                    parent / 'setup.py',
                    parent / '.git',
                    parent / 'requirements.txt'
                ]
                
                if any(indicator.exists() for indicator in dev_indicators):
                    return True
            
            return False
        except Exception:
            # If we can't determine, assume global mode
            return False
    
    def _validate_required_environment_variables(self):
        """Validate that all required environment variables are properly set."""
        required_vars = {
            "NOTION_TOKEN": "Notion API integration token",
            "NOTION_BOARD_DB": "Notion database ID for task management", 
            "TASKS_DIR": "Directory for task files"
        }
        
        missing_vars = []
        invalid_vars = []
        
        for var_name, description in required_vars.items():
            value = self.global_config.get(var_name)
            if not value:
                missing_vars.append(f"{var_name} ({description})")
            elif var_name == "TASKS_DIR":
                # Validate TASKS_DIR exists or can be created
                try:
                    tasks_path = Path(value)
                    tasks_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    invalid_vars.append(f"{var_name}: Cannot create directory '{value}' - {e}")
            elif var_name == "NOTION_BOARD_DB":
                # Basic validation for database ID format
                if not self.global_config.validate_notion_database_id(value):
                    invalid_vars.append(f"{var_name}: Invalid database ID format")
        
        if missing_vars or invalid_vars:
            error_msg = "Application cannot start due to missing/invalid environment variables:\n"
            
            if missing_vars:
                error_msg += "\n❌ Missing required variables:\n"
                for var in missing_vars:
                    error_msg += f"  - {var}\n"
            
            if invalid_vars:
                error_msg += "\n❌ Invalid variable values:\n" 
                for var in invalid_vars:
                    error_msg += f"  - {var}\n"
            
            error_msg += f"\nPlease set these variables in your .env file or environment.\n"
            error_msg += f"Current working directory: {Path.cwd()}\n"
            error_msg += f"Looking for .env file at: {Path.cwd() / '.env'}\n"
            
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def signal_handler(self, signum, frame):
        logger.info("Received shutdown signal. Gracefully stopping...")
        self.running = False
        
        # Cleanup Claude processes if in queued mode
        if hasattr(self, 'claude_invoker'):
            logger.info("🧹 Cleaning up active Claude processes...")
            self.claude_invoker.cleanup_active_processes()
        
        # Cleanup old backup files if in queued mode
        if hasattr(self, 'task_file_manager'):
            logger.info("🧹 Cleaning up old backup files...")
            cleanup_results = self.task_file_manager.cleanup_backups(max_age_days=7)
            logger.info(f"🧹 Cleanup completed: {cleanup_results['cleaned_files']} files removed, {cleanup_results['total_size_freed']} bytes freed")
        
        # Stop polling scheduler if active
        if hasattr(self, 'polling_scheduler'):
            logger.info("⏹️ Requesting polling scheduler shutdown...")
            self.polling_scheduler.request_shutdown()
        
        # Request cancellation for multi-queue processor if active
        if hasattr(self, 'multi_queue_processor'):
            logger.info("⏹️ Requesting multi-queue processor cancellation...")
            self.multi_queue_processor.request_cancellation()
        
        # Log final performance summary before shutdown
        try:
            log_performance_summary()
        except Exception as e:
            logger.warning(f"⚠️ Could not log performance summary during shutdown: {e}")
    
    def process_task_wrapper(self, task):
        """Wrapper function for concurrent task processing (refine mode only)"""
        try:
            if task is None:
                logger.error("Received None task in process_task_wrapper")
                return {
                    "page_id": "unknown",
                    "status": "failed",
                    "error": "Task is None"
                }
            
            result = self.processor.process_task(task, lambda: not self.running)
            return result
        except Exception as e:
            logger.error(f"Exception in concurrent task processing: {e}")
            return {
                "page_id": task.get("id", "unknown") if task is not None else "unknown",
                "status": "failed",
                "error": str(e)
            }
    
    def run_refine_mode(self):
        """Run the refine mode (original main.py functionality)"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("Starting refine mode - processing tasks with 'To Refine' status...")
        
        with PerformanceContext("refine_mode_session"):
            while self.running:
                try:
                    self.stats["last_poll"] = datetime.now()
                    logger.info("="*50)
                    logger.info(f"Polling for tasks with 'To Refine' status...")
                    
                    tasks = self.db_ops.get_tasks_to_refine()
                    
                    # Filter out None tasks to prevent processing errors
                    if tasks:
                        original_count = len(tasks)
                        tasks = [task for task in tasks if task is not None]
                        none_count = original_count - len(tasks)
                        if none_count > 0:
                            logger.warning(f"Filtered out {none_count} None tasks from {original_count} total")
                        
                    
                    if tasks:
                        logger.info(f"Found {len(tasks)} valid tasks to process concurrently")
                        processing_start_time = datetime.now()
                        
                        # Process tasks concurrently using ThreadPoolExecutor
                        max_concurrent_tasks = min(len(tasks), self.max_concurrent_tasks)
                        logger.info(f"Processing {len(tasks)} tasks with {max_concurrent_tasks} concurrent workers (max configured: {self.max_concurrent_tasks})")
                        
                        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
                            # Submit all tasks for concurrent processing
                            future_to_task = {
                                executor.submit(self.process_task_wrapper, task): task 
                                for task in tasks
                            }
                            
                            # Process completed tasks as they finish with responsive shutdown checking
                            completed_tasks = 0
                            while completed_tasks < len(tasks) and self.running:
                                try:
                                    # Use timeout to check for shutdown periodically
                                    done_futures = []
                                    for future in concurrent.futures.as_completed(future_to_task, timeout=1.0):
                                        done_futures.append(future)
                                        completed_tasks += 1
                                        break  # Process one task at a time to check shutdown frequently
                                    
                                    if not done_futures:
                                        continue  # Timeout occurred, check shutdown and continue
                                    
                                    future = done_futures[0]
                                    task = future_to_task[future]
                                    
                                    try:
                                        result = future.result()
                                        
                                        if result["status"] == "completed":
                                            self.stats["tasks_processed"] += 1
                                            task_display_id = result.get('task_id', result.get('page_id', 'unknown'))
                                            logger.info(f"✅ Task {task_display_id} processed successfully")
                                        elif result["status"] == "failed":
                                            self.stats["tasks_failed"] += 1
                                            task_display_id = result.get('task_id', result.get('page_id', 'unknown'))
                                            logger.error(f"❌ Task {task_display_id} failed: {result.get('error', 'Unknown error')}")
                                        elif result["status"] == "aborted":
                                            task_display_id = result.get('task_id', result.get('page_id', 'unknown'))
                                            logger.info(f"⏹️  Task {task_display_id} aborted due to shutdown")
                                        elif result["status"] == "skipped":
                                            task_display_id = result.get('task_id', result.get('page_id', 'unknown'))
                                            logger.info(f"⏭️  Task {task_display_id} skipped: {result.get('message', 'No reason provided')}")
                                            
                                    except concurrent.futures.CancelledError:
                                        logger.info(f"⏹️  Task {task.get('id', 'unknown')} was cancelled due to shutdown")
                                    except Exception as e:
                                        self.stats["tasks_failed"] += 1
                                        logger.error(f"❌ Unexpected error processing task {task.get('id', 'unknown')}: {e}")
                                        
                                except concurrent.futures.TimeoutError:
                                    # Timeout is expected - allows us to check shutdown flag
                                    continue
                            
                            # Cancel any remaining tasks if shutdown was requested
                            if not self.running:
                                logger.info("Shutdown requested, cancelling remaining tasks...")
                                for remaining_future in future_to_task:
                                    if not remaining_future.done():
                                        remaining_future.cancel()
                        
                        processing_duration = datetime.now() - processing_start_time
                        logger.info(f"🏁 Completed concurrent processing of {len(tasks)} tasks in {processing_duration}")
                        
                        # Log performance summary
                        if len(tasks) > 1:
                            avg_time_per_task = processing_duration.total_seconds() / len(tasks)
                            logger.info(f"📊 Average processing time per task: {avg_time_per_task:.2f} seconds")
                            logger.info(f"🚀 Concurrent processing efficiency: {max_concurrent_tasks}x parallelization")
                    else:
                        logger.info("No tasks found with 'To Refine' status")
                    
                    self.log_statistics()
                    
                    # Exit after one run instead of continuous loop
                    logger.info("Refine mode completed - exiting")
                    self.running = False
                    
                except Exception as e:
                    logger.error(f"Error in refine mode: {e}")
                    self.running = False
        
        logger.info("Refine mode stopped")
        self.log_final_statistics()
    
    def run_prepare_mode(self):
        """Run the prepare mode (original main_workflow.py functionality)"""
        logger.info("🚀 Starting prepare mode - NotionTaskMasterWorkflow")
        
        with PerformanceContext("prepare_mode_session"):
            workflow_results = {
            "step_results": {},
            "overall_success": False,
            "successful_tickets": [],
            "failed_tickets": [],
            "summary": {}
        }
        
        try:
            logger.info("🎬 Starting complete Notion-TaskMaster workflow...")
            
            # Step 1: Query tickets with 'Prepare Tasks' status
            logger.info("📋 Step 1: Querying tickets with 'Prepare Tasks' status...")
            prepare_tasks_pages = self.notion_client.query_tickets_by_status("Prepare Tasks")
            workflow_results["step_results"]["query_tickets"] = {
                "pages_found": len(prepare_tasks_pages),
                "pages": prepare_tasks_pages
            }
            
            if not prepare_tasks_pages:
                logger.info("ℹ️  No tickets found with 'Prepare Tasks' status")
                workflow_results["summary"] = {
                    "message": "No tickets to process",
                    "total_tickets": 0,
                    "successful_tickets": 0,
                    "failed_tickets": 0
                }
                return workflow_results
            
            # Step 2: Extract ticket IDs
            logger.info("🔍 Step 2: Extracting ticket IDs from page properties...")
            ticket_ids = self.notion_client.extract_ticket_ids(prepare_tasks_pages)
            workflow_results["step_results"]["extract_ids"] = {
                "extracted_ids": ticket_ids,
                "count": len(ticket_ids)
            }
            
            # Step 3: Validate files exist
            logger.info("📁 Step 3: Validating corresponding markdown files exist...")
            valid_ticket_ids = self.file_ops.validate_task_files(ticket_ids)
            workflow_results["step_results"]["validate_files"] = {
                "valid_ids": valid_ticket_ids,
                "valid_count": len(valid_ticket_ids),
                "invalid_count": len(ticket_ids) - len(valid_ticket_ids)
            }
            
            if not valid_ticket_ids:
                logger.warning("⚠️ No valid ticket files found")
                workflow_results["summary"] = {
                    "message": "No valid tickets to process",
                    "total_tickets": len(ticket_ids),
                    "successful_tickets": 0,
                    "failed_tickets": len(ticket_ids)
                }
                return workflow_results
            
            # IMPORTANT: Process only one ticket at a time to avoid tasks.json conflicts
            if len(valid_ticket_ids) > 1:
                logger.info(f"📝 Found {len(valid_ticket_ids)} valid tickets. Processing only the first one to avoid tasks.json conflicts.")
                logger.info(f"🔄 Remaining tickets will be processed in subsequent runs: {valid_ticket_ids[1:]}")
                valid_ticket_ids = [valid_ticket_ids[0]]  # Process only the first ticket
            
            # Create mapping of valid tickets to their page data (only for the selected ticket)
            valid_page_data = []
            for page in prepare_tasks_pages:
                page_ticket_ids = self.notion_client.extract_ticket_ids([page])
                if page_ticket_ids and page_ticket_ids[0] in valid_ticket_ids:
                    valid_page_data.append({
                        "page_id": page["id"],
                        "ticket_id": page_ticket_ids[0],
                        "page_data": page
                    })
            
            logger.info(f"🎯 Processing single ticket: {valid_ticket_ids[0]} (page_id: {valid_page_data[0]['page_id'] if valid_page_data else 'unknown'})")
            
            # Step 4: Update status to 'Preparing Tasks'
            logger.info("🔄 Step 4: Updating ticket status to 'Preparing Tasks'...")
            page_ids = [item["page_id"] for item in valid_page_data]
            status_update_results = self.notion_client.update_tickets_status_batch(page_ids, "Preparing Tasks")
            workflow_results["step_results"]["update_to_preparing"] = status_update_results
            
            # Step 5: Execute task-master commands
            logger.info("⚡ Step 5: Executing task-master parse-prd commands...")
            command_results = self.cmd_executor.execute_taskmaster_command(valid_ticket_ids)
            workflow_results["step_results"]["execute_commands"] = command_results
            
            # Step 6: Copy tasks.json files (only for successfully parsed tickets)
            logger.info("📋 Step 6: Copying generated tasks.json files...")
            successful_ticket_ids = [item["ticket_id"] for item in command_results["successful_executions"]]
            
            # Validate that we actually have successful parsing results
            if not successful_ticket_ids:
                logger.warning("⚠️ No tickets were successfully parsed - cannot proceed with copying files")
                
                # Update failed tickets to "Failed" status only if parsing actually failed
                failed_ticket_ids = [item["ticket_id"] for item in command_results["failed_executions"]]
                if failed_ticket_ids:
                    logger.info(f"❌ Marking {len(failed_ticket_ids)} failed tickets as 'Failed' status...")
                    failed_page_ids = []
                    for ticket_data in valid_page_data:
                        if ticket_data["ticket_id"] in failed_ticket_ids:
                            failed_page_ids.append(ticket_data["page_id"])
                    
                    if failed_page_ids:
                        revert_results = self.notion_client.update_tickets_status_batch(failed_page_ids, "Failed")
                        logger.info(f"❌ Marked {revert_results.get('success_count', 0)} tickets as 'Failed'")
                
                workflow_results["summary"] = {
                    "message": "Task parsing failed - no valid tasks generated",
                    "total_tickets": len(prepare_tasks_pages),
                    "successful_tickets": 0,
                    "failed_tickets": len(prepare_tasks_pages),
                    "error": "Task parsing validation failed"
                }
                return workflow_results
            
            # Construct path to .taskmaster/tasks/tasks.json relative to FileOperations base_dir
            taskmaster_tasks_path = os.path.join(self.project_root, ".taskmaster", "tasks", "tasks.json")
            # Construct absolute path to tasks subdirectory  
            tasks_dest_dir = os.path.join(get_tasks_dir(), "tasks")
            copy_results = self.file_ops.copy_tasks_file(successful_ticket_ids, source_path=taskmaster_tasks_path, dest_dir=tasks_dest_dir)
            workflow_results["step_results"]["copy_files"] = copy_results
            
            # Handle partially failed tickets - mark failed ones as "Failed" (valid transition)
            failed_ticket_ids = [item["ticket_id"] for item in command_results["failed_executions"]]
            if failed_ticket_ids:
                logger.warning(f"⚠️ {len(failed_ticket_ids)} tickets failed parsing - marking as 'Failed'...")
                failed_page_ids = []
                for ticket_data in valid_page_data:
                    if ticket_data["ticket_id"] in failed_ticket_ids:
                        failed_page_ids.append(ticket_data["page_id"])
                
                if failed_page_ids:
                    revert_results = self.notion_client.update_tickets_status_batch(failed_page_ids, "Failed")
                    logger.info(f"❌ Marked {revert_results.get('success_count', 0)} failed tickets as 'Failed'")
                    workflow_results["step_results"]["mark_failed"] = revert_results
            
            # Step 7: Upload JSON files to Notion pages
            logger.info("📤 Step 7: Uploading JSON files to Notion page Tasks property...")
            # Prepare data for upload
            upload_data = []
            for ticket_data in valid_page_data:
                ticket_id = ticket_data["ticket_id"]
                if ticket_id in successful_ticket_ids:
                    # Get the full ticket ID format for the file path
                    full_ticket_id = self.file_ops._get_full_ticket_id(ticket_id)
                    upload_data.append({
                        "ticket_id": ticket_id,
                        "page_id": ticket_data["page_id"],
                        "tasks_file_path": os.path.join(get_tasks_dir(), "tasks", f"{full_ticket_id}.json")
                    })
            
            upload_results = self.notion_client.upload_tasks_files_to_pages(upload_data)
            workflow_results["step_results"]["upload_files"] = upload_results
            
            # Step 8: Finalize status to 'Ready to Run'
            logger.info("🏁 Step 8: Finalizing ticket status to 'Ready to Run'...")
            successful_upload_data = []
            for upload_item in upload_results["successful_uploads"]:
                # Find the corresponding ticket data
                for ticket_data in valid_page_data:
                    if ticket_data["ticket_id"] == upload_item["ticket_id"]:
                        successful_upload_data.append({
                            "ticket_id": upload_item["ticket_id"],
                            "page_id": upload_item["page_id"],
                            "tasks_file_path": upload_item["file_path"]
                        })
                        break
            
            finalize_results = self.notion_client.finalize_ticket_status(successful_upload_data)
            workflow_results["step_results"]["finalize_status"] = finalize_results
            
            # Compile overall results
            total_tickets = len(prepare_tasks_pages)
            successful_tickets = finalize_results["success_count"]
            failed_tickets = total_tickets - successful_tickets
            
            workflow_results["overall_success"] = successful_tickets > 0
            workflow_results["successful_tickets"] = [item["ticket_id"] for item in finalize_results["finalized_tickets"]]
            workflow_results["failed_tickets"] = [item["ticket_id"] for item in finalize_results["failed_finalizations"]]
            
            workflow_results["summary"] = {
                "message": f"Workflow completed: {successful_tickets} successful, {failed_tickets} failed",
                "total_tickets": total_tickets,
                "successful_tickets": successful_tickets,
                "failed_tickets": failed_tickets,
                "success_rate": (successful_tickets / total_tickets * 100) if total_tickets > 0 else 0
            }
            
            # Final summary logging
            logger.info("🎉 Complete workflow finished!")
            logger.info(f"📊 Final Summary:")
            logger.info(f"   📋 Total tickets processed: {total_tickets}")
            logger.info(f"   ✅ Successful completions: {successful_tickets}")
            logger.info(f"   ❌ Failed completions: {failed_tickets}")
            logger.info(f"   📊 Success rate: {workflow_results['summary']['success_rate']:.1f}%")
            
            if workflow_results["successful_tickets"]:
                logger.info(f"   🎯 Successful ticket IDs: {workflow_results['successful_tickets']}")
            
            if workflow_results["failed_tickets"]:
                logger.warning(f"   ⚠️ Failed ticket IDs: {workflow_results['failed_tickets']}")
            
        except Exception as e:
            logger.error(f"❌ Workflow failed with error: {e}")
            workflow_results["summary"] = {
                "message": f"Workflow failed: {str(e)}",
                "total_tickets": 0,
                "successful_tickets": 0,
                "failed_tickets": 0,
                "error": str(e)
            }
        
        return workflow_results
    
    def _process_queued_tasks_callback(self) -> Dict[str, Any]:
        """
        Callback method for processing queued tasks using simple processor.
        
        Returns:
            Dictionary with processing results
        """
        try:
            # Use the simple queued processor
            success = self.simple_processor.process_queued_tasks()
            
            return {
                "step_results": {"simple_processor": success},
                "overall_success": success,
                "successful_tickets": [],
                "failed_tickets": [],
                "summary": {
                    "message": f"Simple queued processing {'completed successfully' if success else 'failed'}",
                    "total_tickets": 1 if success else 0,
                    "successful_tickets": 1 if success else 0,
                    "failed_tickets": 0 if success else 1,
                    "success_rate": 100.0 if success else 0.0
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Simple queued task processing failed: {e}")
            return {
                "step_results": {},
                "overall_success": False,
                "successful_tickets": [],
                "failed_tickets": [],
                "summary": {
                    "message": f"Simple queued processing failed: {str(e)}",
                    "total_tickets": 0,
                    "successful_tickets": 0,
                    "failed_tickets": 0,
                    "error": str(e)
                }
            }
    
    def run_queued_mode(self):
        """Run the queued mode using simple processor"""
        logger.info("🚀 Starting simple queued mode...")
        
        with PerformanceContext("queued_mode_session"):
            try:
                # Process queued tasks using simple processor
                success = self.simple_processor.process_queued_tasks()
                
                return {
                    "step_results": {"simple_processor": success},
                    "overall_success": success,
                    "successful_tickets": [],
                    "failed_tickets": [],
                    "summary": {
                        "message": f"Simple queued processing {'completed successfully' if success else 'failed'}",
                        "total_tickets": 1 if success else 0,
                        "successful_tickets": 1 if success else 0,
                        "failed_tickets": 0 if success else 1,
                        "success_rate": 100.0 if success else 0.0
                    }
                }
                    
            except Exception as e:
                logger.error(f"❌ Queued mode failed with error: {e}")
                return self._get_failed_result(str(e))
            finally:
                # Log comprehensive performance summary
                log_performance_summary()
    
    def _get_failed_result(self, error_message: str) -> Dict[str, Any]:
        """Helper method to return consistent failure result format."""
        return {
            "step_results": {},
            "overall_success": False,
            "successful_tickets": [],
            "failed_tickets": [],
            "summary": {
                "message": f"Queued mode failed: {error_message}",
                "total_tickets": 0,
                "successful_tickets": 0,
                "failed_tickets": 0,
                "error": error_message
            }
        }
    
    
    def run_continuous_polling_mode(self):
        """Run continuous polling mode when no arguments provided - now uses multi-status processing"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("🔄 Starting continuous polling mode - checking for tasks across all statuses every minute...")
        
        # Initialize multi-status processor for continuous mode
        multi_processor = MultiStatusProcessor(self.project_root)
        
        with PerformanceContext("continuous_polling_session"):
            poll_count = 0
            successful_polls = 0
            
            while self.running:
                try:
                    poll_count += 1
                    self.stats["last_poll"] = datetime.now()
                    logger.info(f"📡 Poll #{poll_count} - Checking for tasks across all statuses...")
                    
                    # Get processing recommendations first
                    recommendations = multi_processor.get_processing_recommendations()
                    
                    # Log current distribution
                    if poll_count % 5 == 1:  # Every 5th poll
                        logger.info("📊 Current task distribution:")
                        for status, count in recommendations["distribution"].items():
                            if count > 0:
                                logger.info(f"   {status}: {count}")
                    
                    # Process priority statuses if they have tasks
                    priority_statuses = [item["status"] for item in recommendations["priority_statuses"]]
                    
                    if priority_statuses:
                        # Convert string status names to TaskStatus enums
                        from utils.task_status import TaskStatus
                        include_statuses = {TaskStatus(status) for status in priority_statuses}
                        
                        # Process priority statuses
                        result = multi_processor.process_all_statuses(include_statuses=include_statuses)
                        
                        if result["overall_success"] and result["summary"]["total_processed"] > 0:
                            successful_polls += 1
                            logger.info(f"✅ Poll #{poll_count} completed successfully - processed {result['summary']['total_processed']} tasks")
                        else:
                            logger.info(f"ℹ️  Poll #{poll_count} completed - no tasks processed")
                    else:
                        logger.info(f"ℹ️  Poll #{poll_count} - no priority tasks found")
                    
                    # Log statistics every 10 polls
                    if poll_count % 10 == 0:
                        success_rate = (successful_polls / poll_count) * 100
                        logger.info(f"📊 Polling Statistics: {successful_polls}/{poll_count} successful ({success_rate:.1f}%)")
                    
                    # Wait 1 minute before next poll (check shutdown every 5 seconds)
                    for _ in range(12):  # 12 * 5 = 60 seconds
                        if not self.running:
                            break
                        time.sleep(5)
                    
                except Exception as e:
                    logger.error(f"❌ Error during poll #{poll_count}: {e}")
                    # Wait before retrying
                    time.sleep(30)
        
        logger.info(f"🏁 Continuous polling stopped after {poll_count} polls ({successful_polls} successful)")
        self.log_final_statistics()

    def run_multi_mode(self):
        """Run multi-status processing mode"""
        logger.info("🚀 Starting multi-status processing mode...")
        
        with PerformanceContext("multi_status_session"):
            try:
                # Process all statuses with recommendations
                recommendations = self.multi_processor.get_processing_recommendations()
                
                # Log current distribution
                logger.info("📊 Current task distribution:")
                for status, count in recommendations["distribution"].items():
                    if count > 0:
                        logger.info(f"   {status}: {count}")
                
                # Process priority statuses
                priority_statuses = [item["status"] for item in recommendations["priority_statuses"]]
                
                if priority_statuses:
                    from utils.task_status import TaskStatus
                    include_statuses = {TaskStatus(status) for status in priority_statuses}
                    
                    result = self.multi_processor.process_all_statuses(include_statuses=include_statuses)
                    
                    return result
                else:
                    logger.info("ℹ️  No priority tasks found to process")
                    return {
                        "overall_success": True,
                        "status_results": {},
                        "summary": {
                            "total_processed": 0,
                            "successful": 0,
                            "failed": 0,
                            "success_rate": 0.0
                        }
                    }
                    
            except Exception as e:
                logger.error(f"❌ Multi-status mode failed: {e}")
                return {
                    "overall_success": False,
                    "status_results": {},
                    "summary": {
                        "total_processed": 0,
                        "successful": 0,
                        "failed": 1,
                        "success_rate": 0.0,
                        "error": str(e)
                    }
                }

    def run(self):
        """Run the application based on mode"""
        if self.mode == "refine":
            self.run_refine_mode()
        elif self.mode == "prepare":
            results = self.run_prepare_mode()
            
            # Exit with appropriate code
            if results["overall_success"]:
                logger.info("✅ Prepare mode completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ Prepare mode completed with errors")
                sys.exit(1)
        elif self.mode == "queued":
            results = self.run_queued_mode()
            
            # Exit with appropriate code
            if results["overall_success"]:
                logger.info("✅ Queued mode completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ Queued mode completed with errors")
                sys.exit(1)
        elif self.mode == "multi":
            results = self.run_multi_mode()
            
            # Exit with appropriate code
            if results["overall_success"]:
                logger.info("✅ Multi-status mode completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ Multi-status mode completed with errors")
                sys.exit(1)
    
    def log_statistics(self):
        runtime = datetime.now() - self.stats["start_time"]
        logger.info(f"Statistics - Processed: {self.stats['tasks_processed']}, Failed: {self.stats['tasks_failed']}, Runtime: {runtime}")
    
    def log_final_statistics(self):
        runtime = datetime.now() - self.stats["start_time"]
        logger.info("="*50)
        logger.info("Final Statistics:")
        logger.info(f"  Total runtime: {runtime}")
        logger.info(f"  Tasks processed: {self.stats['tasks_processed']}")
        logger.info(f"  Tasks failed: {self.stats['tasks_failed']}")
        logger.info(f"  Success rate: {self.stats['tasks_processed'] / (self.stats['tasks_processed'] + self.stats['tasks_failed']) * 100 if (self.stats['tasks_processed'] + self.stats['tasks_failed']) > 0 else 0:.2f}%")
        logger.info("="*50)


def main():
    parser = argparse.ArgumentParser(
        description="Nomad - Notion API integration application with global installation support",
        epilog="""Examples:
  nomad                    # Continuous polling mode (multi-status)
  nomad --refine          # Process 'To Refine' status tasks
  nomad --prepare         # Process 'Prepare Tasks' status
  nomad --queued          # Process 'Queued to run' status tasks
  nomad --multi           # Multi-status mode
  nomad --config-help     # Show configuration help
  nomad --config-create   # Create configuration template
  nomad --status          # Show configuration status""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Mode selection arguments
    parser.add_argument("--refine", action="store_true", help="Run in refine mode (process 'To Refine' status tasks)")
    parser.add_argument("--prepare", action="store_true", help="Run in prepare mode (process 'Prepare Tasks' status)")
    parser.add_argument("--queued", action="store_true", help="Run in queued mode (process 'Queued to run' status tasks only)")
    parser.add_argument("--multi", action="store_true", help="Run in multi-status mode (process multiple status types)")
    
    # Configuration and management arguments
    parser.add_argument("--config-help", action="store_true", help="Show configuration help and requirements")
    parser.add_argument("--config-create", action="store_true", help="Create a configuration template file")
    parser.add_argument("--config-status", action="store_true", help="Show current configuration status")
    parser.add_argument("--health-check", action="store_true", help="Perform comprehensive health check")
    parser.add_argument("--working-dir", help="Set working directory (default: current directory)")
    parser.add_argument("--version", action="version", version="Nomad v0.2.0 - Notion Automation Tool")
    
    args = parser.parse_args()
    
    # Handle configuration management commands first
    if args.config_help:
        show_config_help()
        return
    
    if args.config_create:
        create_config_template(args.working_dir)
        return
    
    if args.config_status:
        show_config_status(args.working_dir)
        return
    
    if args.health_check:
        perform_health_check(args.working_dir)
        return
    
    # Set working directory if specified
    if args.working_dir:
        os.chdir(args.working_dir)
        print(f"Changed working directory to: {args.working_dir}")
    
    # Determine mode
    mode_count = sum([args.refine, args.prepare, args.queued, args.multi])
    if mode_count > 1:
        logger.error("Cannot specify multiple modes")
        logger.error("Usage: uv run main.py [--refine|--prepare|--queued|--multi]")
        sys.exit(1)
    elif args.refine:
        mode = "refine"
        app = NotionDeveloper(mode=mode)
        app.run()
    elif args.prepare:
        mode = "prepare"
        app = NotionDeveloper(mode=mode)
        app.run()
    elif args.queued:
        # Handle queued mode directly with simple processor
        project_root = os.path.dirname(os.path.dirname(__file__))
        processor = SimpleQueuedProcessor(project_root)
        success = processor.process_queued_tasks()
        sys.exit(0 if success else 1)
    elif args.multi:
        mode = "multi"
        app = NotionDeveloper(mode=mode)
        app.run()
    else:
        # No arguments provided - run continuous polling mode with multi-status processing
        logger.info("No mode specified - starting continuous polling mode")
        project_root = os.path.dirname(os.path.dirname(__file__))
        app = NotionDeveloper(mode="queued")  # Initialize with basic mode
        app.run_continuous_polling_mode()  # But use multi-status continuous polling


def show_config_help():
    """Show configuration help and setup instructions."""
    print("🔧 Nomad Configuration Help")
    print("=" * 50)
    print()
    print("Nomad requires several environment variables to function properly.")
    print("You can set these in:")
    print("  1. Your shell environment (export VAR=value)")
    print("  2. A .env file in your working directory")
    print("  3. A global config file (use --config-create)")
    print()
    
    # Get global config to show requirements
    try:
        config = get_global_config()
        summary = config.get_config_summary()
        
        required_vars = []
        optional_vars = []
        
        for var_name, info in summary.items():
            if info['required']:
                required_vars.append((var_name, info['description']))
            else:
                optional_vars.append((var_name, info['description']))
        
        print("📋 Required Environment Variables:")
        print("-" * 40)
        for var_name, description in required_vars:
            print(f"  {var_name}")
            print(f"    {description}")
            print()
        
        print("📋 Optional Environment Variables:")
        print("-" * 40)
        for var_name, description in optional_vars:
            print(f"  {var_name}")
            print(f"    {description}")
            print()
        
        print("💡 Quick Setup:")
        print("  1. Run: nomad --config-create")
        print("  2. Edit the created config file")
        print("  3. Set NOMAD_CONFIG_FILE environment variable")
        print("  4. Run: nomad --config-status")
        
    except Exception as e:
        print(f"Error loading configuration: {e}")

def create_config_template(working_dir: Optional[str] = None):
    """Create a configuration template file."""
    try:
        if working_dir:
            os.chdir(working_dir)
        
        config = get_global_config()
        template_path = config.create_global_config_template()
        
        print(f"✅ Configuration template created: {template_path}")
        print()
        print("Next steps:")
        print(f"  1. Edit the file: {template_path}")
        print("  2. Set required values (marked as REQUIRED)")
        print(f"  3. Set environment variable: export NOMAD_CONFIG_FILE={template_path}")
        print("  4. Test with: nomad --config-status")
        
    except Exception as e:
        print(f"❌ Error creating config template: {e}")
        sys.exit(1)

def show_config_status(working_dir: Optional[str] = None):
    """Show current configuration status."""
    try:
        if working_dir:
            os.chdir(working_dir)
        
        config = get_global_config()
        summary = config.get_config_summary()
        issues = config.validate_working_environment()
        
        print("🔍 Configuration Status")
        print("=" * 50)
        print()
        
        # Show directories
        print("📁 Directories:")
        print(f"  Home: {config.get_home_directory()}")
        print(f"  Tasks: {config.get_tasks_directory()}")
        print(f"  Working: {Path.cwd()}")
        print()
        
        # Show configuration status
        print("⚙️  Configuration Variables:")
        print("-" * 30)
        for var_name, info in summary.items():
            status_icon = "✅" if info['set'] else ("❌" if info['required'] else "⚪")
            required_text = " (REQUIRED)" if info['required'] else ""
            value_text = info['value'] if info['value'] else "Not set"
            
            print(f"  {status_icon} {var_name}{required_text}")
            print(f"      Value: {value_text}")
            print(f"      Description: {info['description']}")
            print()
        
        # Show validation issues
        if issues:
            print("⚠️  Issues Found:")
            print("-" * 20)
            for issue in issues:
                print(f"  ❌ {issue}")
            print()
        else:
            print("✅ No configuration issues found!")
            print()
        
        # Show API key status
        available_providers = config.get_available_providers()
        if available_providers:
            print(f"🔑 Available AI Providers: {', '.join(available_providers)}")
        else:
            print("⚠️  No AI API keys configured. At least one is recommended.")
        
    except Exception as e:
        print(f"❌ Error checking configuration status: {e}")
        sys.exit(1)

def perform_health_check(working_dir: Optional[str] = None):
    """Perform comprehensive health check of the Nomad installation."""
    try:
        if working_dir:
            os.chdir(working_dir)
        
        print("🏥 Nomad Health Check")
        print("=" * 50)
        print()
        
        health_status = {
            "overall_healthy": True,
            "checks": {},
            "warnings": [],
            "errors": []
        }
        
        # 1. System Requirements Check
        print("🔍 System Requirements:")
        print("-" * 25)
        
        # Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if sys.version_info >= (3, 8):
            print(f"  ✅ Python {python_version} (>= 3.8 required)")
            health_status["checks"]["python_version"] = True
        else:
            print(f"  ❌ Python {python_version} (3.8+ required)")
            health_status["checks"]["python_version"] = False
            health_status["overall_healthy"] = False
            health_status["errors"].append(f"Python version {python_version} is too old")
        
        print()
        
        # 2. Configuration Check
        print("⚙️  Configuration:")
        print("-" * 20)
        
        config = get_global_config(strict_validation=False)
        
        # Required configuration
        required_vars = ["NOTION_TOKEN", "NOTION_BOARD_DB"]
        for var in required_vars:
            value = config.get(var)
            if value:
                print(f"  ✅ {var} configured")
                health_status["checks"][var.lower()] = True
            else:
                print(f"  ❌ {var} not configured")
                health_status["checks"][var.lower()] = False
                health_status["overall_healthy"] = False
                health_status["errors"].append(f"{var} is required but not configured")
        
        # API Keys
        api_keys = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"]
        valid_api_keys = []
        for api_key in api_keys:
            value = config.get(api_key)
            if value:
                provider = api_key.replace("_API_KEY", "").lower()
                is_valid, issues = config.security_manager.validate_api_key_format(provider, value)
                if is_valid:
                    print(f"  ✅ {api_key} configured and valid")
                    valid_api_keys.append(provider)
                    health_status["checks"][api_key.lower()] = True
                else:
                    print(f"  ⚠️  {api_key} configured but format issues: {'; '.join(issues)}")
                    health_status["checks"][api_key.lower()] = False
                    health_status["warnings"].append(f"{api_key} format issues")
            else:
                print(f"  ⚪ {api_key} not configured")
                health_status["checks"][api_key.lower()] = False
        
        if not valid_api_keys:
            print("  ❌ No valid AI API keys found")
            health_status["overall_healthy"] = False
            health_status["errors"].append("At least one valid AI API key is required")
        else:
            print(f"  ✅ Valid API keys: {', '.join(valid_api_keys)}")
        
        print()
        
        # 3. Directory Access Check
        print("📁 Directory Access:")
        print("-" * 20)
        
        directories = [
            ("Home", config.get_home_directory()),
            ("Tasks", config.get_tasks_directory()),
            ("Working", Path.cwd())
        ]
        
        for name, path in directories:
            try:
                path_obj = Path(path)
                if path_obj.exists():
                    if os.access(path, os.R_OK | os.W_OK):
                        print(f"  ✅ {name}: {path} (readable/writable)")
                        health_status["checks"][f"{name.lower()}_directory"] = True
                    else:
                        print(f"  ❌ {name}: {path} (permission denied)")
                        health_status["checks"][f"{name.lower()}_directory"] = False
                        health_status["overall_healthy"] = False
                        health_status["errors"].append(f"Cannot access {name} directory")
                else:
                    try:
                        path_obj.mkdir(parents=True, exist_ok=True)
                        print(f"  ✅ {name}: {path} (created)")
                        health_status["checks"][f"{name.lower()}_directory"] = True
                    except PermissionError:
                        print(f"  ❌ {name}: {path} (cannot create)")
                        health_status["checks"][f"{name.lower()}_directory"] = False
                        health_status["overall_healthy"] = False
                        health_status["errors"].append(f"Cannot create {name} directory")
            except Exception as e:
                print(f"  ❌ {name}: {path} (error: {e})")
                health_status["checks"][f"{name.lower()}_directory"] = False
                health_status["overall_healthy"] = False
                health_status["errors"].append(f"Directory error for {name}: {e}")
        
        print()
        
        # 4. Overall Status
        print("📊 Overall Status:")
        print("-" * 20)
        
        if health_status["overall_healthy"]:
            print("  ✅ System is healthy and ready to use!")
        else:
            print("  ❌ System has critical issues that need attention")
        
        if health_status["warnings"]:
            print(f"  ⚠️  {len(health_status['warnings'])} warnings found")
        
        if health_status["errors"]:
            print(f"  ❌ {len(health_status['errors'])} errors found")
        
        print()
        
        # 5. Recommendations
        if health_status["errors"] or health_status["warnings"]:
            print("💡 Recommendations:")
            print("-" * 20)
            
            for error in health_status["errors"]:
                print(f"  🔴 Critical: {error}")
            
            for warning in health_status["warnings"]:
                print(f"  🟡 Warning: {warning}")
            
            print()
            print("  Run the following commands for help:")
            print("    nomad --config-help     # Configuration assistance")
            print("    nomad --config-create   # Create config template")
            print("    nomad --config-status   # Check configuration")
            print()
        
        if health_status["overall_healthy"]:
            print("🎉 Ready to run! Try:")
            print("  nomad --help           # Show all available commands")
            print("  nomad --refine         # Process Notion tasks")
            
        return health_status["overall_healthy"]
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

if __name__ == "__main__":
    main()