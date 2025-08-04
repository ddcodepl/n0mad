#!/usr/bin/env python3
"""
Combined main application for Notion API integration
Supports two modes:
1. --refine: Process tasks with 'To Refine' status (original main.py functionality)
2. --prepare: Process tasks with 'Prepare Tasks' status (original main_workflow.py functionality)
"""
import os
import sys
import time
import signal
import logging
import argparse
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

from notion_wrapper import NotionClientWrapper
from openai_client import OpenAIClient
from database_operations import DatabaseOperations
from content_processor import ContentProcessor
from file_operations import FileOperations
from command_executor import CommandExecutor
from status_transition_manager import StatusTransitionManager
from feedback_manager import FeedbackManager, ProcessingStage
from claude_engine_invoker import ClaudeEngineInvoker, InvocationResult
from task_file_manager import TaskFileManager, CopyResult
from multi_queue_processor import MultiQueueProcessor
from polling_scheduler import PollingScheduler, CircuitBreakerConfig
from performance_integration import (
    initialize_performance_monitoring, 
    integrate_all_components,
    log_performance_summary,
    PerformanceContext
)
from logging_config import get_logger
from config import config_manager
from simple_queued_processor import SimpleQueuedProcessor

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nomad.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class NotionDeveloper:
    def __init__(self, mode="refine"):
        self.mode = mode
        self.running = True
        self.max_concurrent_tasks = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
        self.stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "start_time": datetime.now(),
            "last_poll": None
        }
        
        try:
            logger.info(f"Initializing Notion Developer application in {mode} mode...")
            
            # Calculate project root consistently for both modes
            # Task-master needs to run from project root where .taskmaster is located
            self.project_root = os.path.dirname(os.path.dirname(__file__))  # Go up from src to project root
            
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
                self.file_ops = FileOperations(base_dir=os.path.join(self.project_root, "src", "tasks"))
                self.db_ops = DatabaseOperations(self.notion_client)
                self.processor = ContentProcessor(self.notion_client, self.openai_client, self.file_ops)
            elif mode == "prepare":
                # Initialize both FileOperations and CommandExecutor with the same project root context
                self.file_ops = FileOperations(base_dir=os.path.join(self.project_root, "src", "tasks"))
                self.cmd_executor = CommandExecutor(base_dir=self.project_root)
            elif mode == "queued":
                # Initialize components needed for queued task processing
                self.file_ops = FileOperations(base_dir=os.path.join(self.project_root, "src", "tasks"))
                self.db_ops = DatabaseOperations(self.notion_client)
                self.cmd_executor = CommandExecutor(base_dir=self.project_root)
                self.status_manager = StatusTransitionManager(self.notion_client)
                self.feedback_manager = FeedbackManager(self.notion_client)
                self.claude_invoker = ClaudeEngineInvoker(self.project_root)
                self.task_file_manager = TaskFileManager(self.project_root)
                self.multi_queue_processor = MultiQueueProcessor(
                    self.db_ops,
                    self.status_manager, 
                    self.feedback_manager,
                    self.claude_invoker,
                    self.task_file_manager,
                    project_root=self.project_root,
                    taskmaster_callback=None  # Will be enhanced when MCP tools are available
                )
                
                # Enable Task Master integration if running in Claude Code environment
                # In a real Claude Code session, this would be automatically detected
                logger.info("🎯 Enabling Task Master AI integration for queued processing")
                self.multi_queue_processor.enable_real_taskmaster_integration(mcp_tools_available=True)
                
                # Initialize polling scheduler for continuous operation
                circuit_breaker_config = CircuitBreakerConfig(
                    failure_threshold=5,
                    recovery_timeout=60,
                    success_threshold=2
                )
                self.polling_scheduler = PollingScheduler(
                    task_processor_callback=self._process_queued_tasks_callback,
                    circuit_breaker_config=circuit_breaker_config
                )
            
            if not self.notion_client.test_connection():
                raise Exception("Failed to connect to Notion database")
            
            logger.info("Application initialized successfully")
            logger.info(f"Configured for {self.max_concurrent_tasks} concurrent task processing")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            sys.exit(1)
    
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
            
            # Create mapping of valid tickets to their page data
            valid_page_data = []
            for page in prepare_tasks_pages:
                page_ticket_ids = self.notion_client.extract_ticket_ids([page])
                if page_ticket_ids and page_ticket_ids[0] in valid_ticket_ids:
                    valid_page_data.append({
                        "page_id": page["id"],
                        "ticket_id": page_ticket_ids[0],
                        "page_data": page
                    })
            
            # Step 4: Update status to 'Preparing Tasks'
            logger.info("🔄 Step 4: Updating ticket status to 'Preparing Tasks'...")
            page_ids = [item["page_id"] for item in valid_page_data]
            status_update_results = self.notion_client.update_tickets_status_batch(page_ids, "Preparing Tasks")
            workflow_results["step_results"]["update_to_preparing"] = status_update_results
            
            # Step 5: Execute task-master commands
            logger.info("⚡ Step 5: Executing task-master parse-prd commands...")
            command_results = self.cmd_executor.execute_taskmaster_command(valid_ticket_ids)
            workflow_results["step_results"]["execute_commands"] = command_results
            
            # Step 6: Copy tasks.json files
            logger.info("📋 Step 6: Copying generated tasks.json files...")
            successful_ticket_ids = [item["ticket_id"] for item in command_results["successful_executions"]]
            # Construct path to .taskmaster/tasks/tasks.json relative to FileOperations base_dir
            taskmaster_tasks_path = os.path.join(self.project_root, ".taskmaster", "tasks", "tasks.json")
            # Construct absolute path to tasks subdirectory  
            tasks_dest_dir = os.path.join(self.project_root, "src", "tasks", "tasks")
            copy_results = self.file_ops.copy_tasks_file(successful_ticket_ids, source_path=taskmaster_tasks_path, dest_dir=tasks_dest_dir)
            workflow_results["step_results"]["copy_files"] = copy_results
            
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
                        "tasks_file_path": os.path.join(self.project_root, "src", "tasks", "tasks", f"{full_ticket_id}.json")
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
        Callback method for polling scheduler to process queued tasks.
        This ensures task outputs are properly saved to src directory.
        
        Returns:
            Dictionary with processing results
        """
        try:
            # Use the multi-queue processor for orchestrated task processing
            processing_session = self.multi_queue_processor.process_queued_tasks(
                cancellation_check=lambda: not self.running
            )
            
            # Build results in expected format for polling scheduler
            result = {
                "step_results": {
                    "session_id": processing_session.session_id,
                    "processing_session": processing_session
                },
                "overall_success": processing_session.successful_tasks > 0,
                "successful_tickets": [],
                "failed_tickets": [],
                "summary": {
                    "message": f"Multi-queue processing completed: {processing_session.successful_tasks} successful, {processing_session.failed_tasks} failed",
                    "total_tickets": processing_session.total_tasks,
                    "successful_tickets": processing_session.successful_tasks,
                    "failed_tickets": processing_session.failed_tasks,
                    "success_rate": (processing_session.successful_tasks / processing_session.total_tasks * 100) if processing_session.total_tasks > 0 else 0
                }
            }
            
            # Extract ticket IDs for tracking
            for processing_result in processing_session.processing_results:
                if processing_result["status"] == "success":
                    result["successful_tickets"].append(processing_result["task_id"])
                else:
                    result["failed_tickets"].append(processing_result["task_id"])
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Queued task processing callback failed: {e}")
            return {
                "step_results": {},
                "overall_success": False,
                "successful_tickets": [],
                "failed_tickets": [],
                "summary": {
                    "message": f"Multi-queue processing failed: {str(e)}",
                    "total_tickets": 0,
                    "successful_tickets": 0,
                    "failed_tickets": 0,
                    "error": str(e)
                }
            }
    
    def run_queued_mode(self):
        """Run the queued mode with continuous polling scheduler"""
        logger.info("🚀 Starting enhanced queued mode with continuous polling scheduler...")
        
        with PerformanceContext("queued_mode_session"):
            try:
                # Check if continuous polling is enabled
                if config_manager.get_enable_continuous_polling():
                    logger.info("🕒 Continuous polling enabled - starting polling scheduler...")
                    
                    # Start the polling scheduler
                    if self.polling_scheduler.start():
                        logger.info("✅ Polling scheduler started successfully")
                        
                        # Keep main thread alive while polling scheduler runs
                        try:
                            while self.running and self.polling_scheduler.is_running():
                                time.sleep(1.0)
                        except KeyboardInterrupt:
                            logger.info("⏹️ Keyboard interrupt received")
                        
                        # Stop the polling scheduler
                        logger.info("⏹️ Stopping polling scheduler...")
                        self.polling_scheduler.stop()
                        
                        # Get final metrics
                        metrics = self.polling_scheduler.get_metrics()
                        logger.info("📊 Final Polling Scheduler Metrics:")
                        logger.info(f"   🔄 Total polls: {metrics['total_polls']}")
                        logger.info(f"   ✅ Successful polls: {metrics['successful_polls']}")
                        logger.info(f"   ❌ Failed polls: {metrics['failed_polls']}")
                        logger.info(f"   📋 Tasks processed: {metrics['tasks_processed']}")
                        logger.info(f"   📊 Success rate: {metrics['success_rate']:.1f}%")
                        logger.info(f"   ⏱️ Average poll duration: {metrics['average_poll_duration']:.2f}s")
                        
                        return {
                            "step_results": {"polling_metrics": metrics},
                            "overall_success": metrics['successful_polls'] > 0,
                            "successful_tickets": [],
                            "failed_tickets": [],
                            "summary": {
                                "message": f"Continuous polling completed: {metrics['successful_polls']} successful polls, {metrics['tasks_processed']} tasks processed",
                                "total_polls": metrics['total_polls'],
                                "successful_polls": metrics['successful_polls'],
                                "failed_polls": metrics['failed_polls'],
                                "tasks_processed": metrics['tasks_processed'],
                                "success_rate": metrics['success_rate']
                            }
                        }
                    else:
                        logger.error("❌ Failed to start polling scheduler")
                        return self._get_failed_result("Failed to start polling scheduler")
                        
                else:
                    logger.info("🔄 Continuous polling disabled - running single processing cycle...")
                    # Single processing cycle when continuous polling is disabled
                    return self._process_queued_tasks_callback()
                    
            except Exception as e:
                logger.error(f"❌ Queued mode failed with error: {e}")
                return self._get_failed_result(str(e))
            finally:
                # Log component statistics
                self._log_enhanced_statistics()
                
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
    
    def _log_enhanced_statistics(self):
        """Log enhanced statistics from all components using multi-queue processor."""
        # Log multi-queue processing statistics
        logger.info("🔄 Multi-Queue Processing Statistics:")
        multi_queue_stats = self.multi_queue_processor.get_processing_statistics()
        logger.info(f"   🚀 Total sessions: {multi_queue_stats['total_sessions']}")
        logger.info(f"   📋 Total tasks processed: {multi_queue_stats['total_tasks_processed']}")
        logger.info(f"   ✅ Successful tasks: {multi_queue_stats['successful_tasks']}")
        logger.info(f"   ❌ Failed tasks: {multi_queue_stats['failed_tasks']}")
        logger.info(f"   📊 Overall success rate: {multi_queue_stats['overall_success_rate']:.1f}%")
        logger.info(f"   ⏱️ Average session duration: {multi_queue_stats['average_session_duration']:.2f}s")
        logger.info(f"   🕒 Total processing time: {multi_queue_stats['total_processing_time']:.2f}s")
        
        # Log status transition statistics
        logger.info("📊 Status Transition Statistics:")
        transition_stats = self.status_manager.get_statistics()
        logger.info(f"   🔄 Total transitions: {transition_stats['total_transitions']}")
        logger.info(f"   ✅ Successful transitions: {transition_stats['successful_transitions']}")
        logger.info(f"   ❌ Failed transitions: {transition_stats['failed_transitions']}")
        logger.info(f"   🔄 Rollbacks attempted: {transition_stats['rollbacks_attempted']}")
        logger.info(f"   ✅ Rollbacks successful: {transition_stats['rollbacks_successful']}")
        logger.info(f"   📊 Transition success rate: {transition_stats['success_rate']:.1f}%")
        if transition_stats['rollbacks_attempted'] > 0:
            logger.info(f"   📊 Rollback success rate: {transition_stats['rollback_success_rate']:.1f}%")
        
        # Log Claude invocation statistics
        logger.info("🤖 Claude Engine Invocation Statistics:")
        claude_stats = self.claude_invoker.get_statistics()
        logger.info(f"   🚀 Total invocations: {claude_stats['total_invocations']}")
        logger.info(f"   ✅ Successful invocations: {claude_stats['successful_invocations']}")
        logger.info(f"   ❌ Failed invocations: {claude_stats['failed_invocations']}")
        logger.info(f"   ⏰ Timeout invocations: {claude_stats['timeout_invocations']}")
        logger.info(f"   📊 Success rate: {claude_stats['success_rate']:.1f}%")
        logger.info(f"   ⏱️ Average duration: {claude_stats['average_duration_seconds']:.2f}s")
        if claude_stats['timeout_rate'] > 0:
            logger.info(f"   ⏰ Timeout rate: {claude_stats['timeout_rate']:.1f}%")
        
        # Log task file copy statistics
        logger.info("📋 Task File Copy Statistics:")
        copy_stats = self.task_file_manager.get_statistics()
        logger.info(f"   📄 Total copy operations: {copy_stats['total_operations']}")
        logger.info(f"   ✅ Successful copies: {copy_stats['successful_operations']}")
        logger.info(f"   ❌ Failed copies: {copy_stats['failed_operations']}")
        logger.info(f"   ⏭️ Skipped copies: {copy_stats['skipped_operations']}")
        logger.info(f"   📊 Copy success rate: {copy_stats['success_rate']:.1f}%")
        logger.info(f"   📏 Total bytes copied: {copy_stats['total_bytes_copied']}")
        logger.info(f"   💾 Backups created: {copy_stats['backups_created']}")
        if copy_stats['rolled_back_operations'] > 0:
            logger.info(f"   🔄 Rollbacks performed: {copy_stats['rolled_back_operations']}")
    
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
        description="Notion API integration application",
        epilog="Examples:\n  uv run main.py --refine\n  uv run main.py --prepare\n  uv run main.py --queued",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--refine", action="store_true", help="Run in refine mode (process 'To Refine' status tasks)")
    parser.add_argument("--prepare", action="store_true", help="Run in prepare mode (process 'Prepare Tasks' status)")
    parser.add_argument("--queued", action="store_true", help="Run in queued mode (process 'Queued to run' status tasks)")
    parser.add_argument("--simple-queued", action="store_true", help="Run in simple queued mode (new simplified logic)")
    
    args = parser.parse_args()
    
    # Determine mode
    mode_count = sum([args.refine, args.prepare, args.queued, args.simple_queued])
    if mode_count > 1:
        logger.error("Cannot specify multiple modes")
        logger.error("Usage: uv run main.py --refine OR uv run main.py --prepare OR uv run main.py --queued OR uv run main.py --simple-queued")
        sys.exit(1)
    elif args.refine:
        mode = "refine"
    elif args.prepare:
        mode = "prepare"
    elif args.queued:
        mode = "queued"
    elif args.simple_queued:
        # Handle simple queued mode directly
        project_root = os.path.dirname(os.path.dirname(__file__))
        processor = SimpleQueuedProcessor(project_root)
        success = processor.process_queued_tasks()
        sys.exit(0 if success else 1)
    else:
        logger.error("Must specify one of: --refine, --prepare, --queued, or --simple-queued mode")
        logger.error("Usage: uv run main.py --refine OR uv run main.py --prepare OR uv run main.py --queued OR uv run main.py --simple-queued")
        sys.exit(1)
    
    app = NotionDeveloper(mode=mode)
    app.run()


if __name__ == "__main__":
    main()