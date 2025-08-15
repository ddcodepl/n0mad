#!/usr/bin/env python3
"""
Multi-status processor that can handle different task statuses beyond just 'Queued to run'.
This processor extends the simple queued processor to handle:
- To Refine: Tasks that need refinement
- Prepare Tasks: Tasks that need task preparation
- Preparing Tasks: Tasks currently being prepared
- Queued to run: Tasks ready for execution (existing functionality)
- Failed: Tasks that failed and need retry
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.clients.notion_wrapper import NotionClientWrapper
from src.clients.openai_client import OpenAIClient
from src.core.managers.status_transition_manager import StatusTransitionManager
from src.core.operations.command_executor import CommandExecutor
from src.core.operations.database_operations import DatabaseOperations
from src.core.processors.content_processor import ContentProcessor
from src.core.processors.simple_queued_processor import SimpleQueuedProcessor
from src.utils.file_operations import FileOperations, get_tasks_dir
from src.utils.logging_config import get_logger
from src.utils.task_status import TaskStatus

logger = get_logger(__name__)


class MultiStatusProcessor:
    """Enhanced processor for handling multiple task statuses."""

    def __init__(self, project_root: str):
        """
        Initialize the multi-status processor.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)

        # Track recently processed tasks to avoid immediate reprocessing
        self._recently_processed_tasks = set()
        self._last_process_time = {}

        # Initialize core components
        self.notion_client = NotionClientWrapper()
        self.db_ops = DatabaseOperations(self.notion_client)
        self.status_manager = StatusTransitionManager(self.notion_client)

        # Initialize mode-specific processors
        self.openai_client = OpenAIClient()
        self.file_ops = FileOperations()  # Will use TASKS_DIR from environment or default to ./tasks
        self.cmd_executor = CommandExecutor(base_dir=str(self.project_root))
        self.content_processor = ContentProcessor(self.notion_client, self.openai_client, self.file_ops)
        self.simple_queued_processor = SimpleQueuedProcessor(str(self.project_root))

        # Status processing configuration
        self.status_processors = {
            TaskStatus.TO_REFINE: self._process_refine_tasks,
            TaskStatus.REFINED: self._process_refined_tasks,  # Add refined tasks processing
            TaskStatus.PREPARE_TASKS: self._process_prepare_tasks,
            TaskStatus.PREPARING_TASKS: self._process_preparing_tasks,
            TaskStatus.READY_TO_RUN: self._process_ready_to_run_tasks,  # Add ready to run tasks
            TaskStatus.QUEUED_TO_RUN: self._process_queued_tasks,
            TaskStatus.FAILED: self._process_failed_tasks,
        }

        # Processing statistics
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "by_status": {},
        }

        logger.info(f"🎯 MultiStatusProcessor initialized")
        logger.info(f"   📁 Project root: {self.project_root}")
        logger.info(f"   🔧 Configured for {len(self.status_processors)} status types")

    def _safe_status_transition(self, task_id: str, expected_from_status: str, to_status: str, task_description: str = "") -> Dict[str, Any]:
        """
        Safely transition a task status by first checking the current actual status
        to handle race conditions and status changes between query and transition.

        Args:
            task_id: The task/page ID to transition
            expected_from_status: The status we expect the task to have
            to_status: The target status to transition to
            task_description: Optional description for logging

        Returns:
            Dict with 'success' (bool), 'message' (str), and optional 'current_status' (str)
        """
        try:
            desc = f" {task_description}" if task_description else ""
            logger.info(f"🔍 Checking current status for{desc} task: {task_id}")

            # Get the current actual status from Notion to handle race conditions
            current_page = self.notion_client.get_page(task_id)
            current_status = self.notion_client._extract_status_from_page(current_page)

            logger.info(f"📋 Task {task_id} current status: '{current_status}', expected: '{expected_from_status}'")

            # Handle based on actual current status
            if current_status == expected_from_status:
                # Status matches expectation - proceed with transition
                logger.info(f"🚀 Transitioning{desc} task {task_id}: '{expected_from_status}' → '{to_status}'")
                transition = self.status_manager.transition_status(page_id=task_id, from_status=expected_from_status, to_status=to_status)

                if transition.result.value == "success":
                    logger.info(f"✅ Successfully transitioned{desc} task {task_id} to '{to_status}'")
                    return {
                        "success": True,
                        "message": f"Successfully transitioned to '{to_status}'",
                        "current_status": to_status,
                    }
                else:
                    logger.error(f"❌ Failed to transition{desc} task {task_id}: {transition.error}")
                    return {
                        "success": False,
                        "message": f"Transition failed: {transition.error}",
                        "current_status": current_status,
                    }

            elif current_status == to_status:
                # Already in target status - this is actually success
                logger.info(f"✅ Task {task_id} already in '{to_status}' status - no action needed")
                return {
                    "success": True,
                    "message": f"Already in target status '{to_status}'",
                    "current_status": current_status,
                }

            else:
                # Unexpected status - determine if this is an error or just a race condition
                logger.warning(f"⚠️ Task {task_id} has unexpected status '{current_status}' (expected '{expected_from_status}')")

                # Check if the current status is a valid "downstream" status that indicates the task has progressed
                valid_downstream_statuses = self._get_downstream_statuses(expected_from_status)

                if current_status in valid_downstream_statuses:
                    logger.info(f"ℹ️  Task {task_id} has progressed beyond expected status - treating as success")
                    return {
                        "success": True,
                        "message": f"Task has progressed to '{current_status}' (beyond '{expected_from_status}')",
                        "current_status": current_status,
                    }
                else:
                    logger.warning(f"⚠️ Task {task_id} status '{current_status}' is not a valid progression from '{expected_from_status}' - skipping")
                    return {
                        "success": False,
                        "message": f"Invalid status progression: '{current_status}' is not downstream from '{expected_from_status}'",
                        "current_status": current_status,
                    }

        except Exception as e:
            logger.error(f"❌ Error in safe status transition for{desc} task {task_id}: {e}")
            return {
                "success": False,
                "message": f"Exception during transition: {str(e)}",
                "current_status": "unknown",
            }

    def _get_downstream_statuses(self, from_status: str) -> List[str]:
        """
        Get list of valid "downstream" statuses that indicate task progression beyond the expected status.

        Args:
            from_status: The status we're transitioning from

        Returns:
            List of status strings that are valid progressions
        """
        # Define the typical workflow progression
        status_flow = {
            "To Refine": [
                "Refined",
                "Prepare Tasks",
                "Preparing Tasks",
                "Ready to run",
                "Queued to run",
                "In progress",
                "Done",
            ],
            "Refined": [
                "Prepare Tasks",
                "Preparing Tasks",
                "Ready to run",
                "Queued to run",
                "In progress",
                "Done",
            ],
            "Prepare Tasks": [
                "Preparing Tasks",
                "Ready to run",
                "Queued to run",
                "In progress",
                "Done",
            ],
            "Preparing Tasks": ["Ready to run", "Queued to run", "In progress", "Done"],
            "Ready to run": ["Queued to run", "In progress", "Done"],
            "Queued to run": ["In progress", "Done"],
            "In progress": ["Done"],
            "Failed": [],  # Failed tasks don't have downstream statuses
        }

        return status_flow.get(from_status, [])

    def process_all_statuses(
        self,
        include_statuses: Optional[Set[TaskStatus]] = None,
        exclude_statuses: Optional[Set[TaskStatus]] = None,
    ) -> Dict[str, Any]:
        """
        Process tasks across multiple statuses.

        Args:
            include_statuses: Only process these statuses (None = all configured)
            exclude_statuses: Skip these statuses (None = no exclusions)

        Returns:
            Dictionary with processing results
        """
        logger.info("🚀 Starting multi-status task processing...")

        # Determine which statuses to process
        statuses_to_process = set(self.status_processors.keys())

        if include_statuses:
            statuses_to_process &= include_statuses
            logger.info(f"📋 Including only statuses: {[s.value for s in include_statuses]}")

        if exclude_statuses:
            statuses_to_process -= exclude_statuses
            logger.info(f"🚫 Excluding statuses: {[s.value for s in exclude_statuses]}")

        if not statuses_to_process:
            logger.warning("⚠️ No statuses to process after filtering")
            return self._get_empty_result()

        logger.info(f"🎯 Processing {len(statuses_to_process)} statuses: {[s.value for s in statuses_to_process]}")

        # Process each status
        overall_results = {"status_results": {}, "overall_success": True, "summary": {}}

        for status in statuses_to_process:
            logger.info(f"📋 Processing status: {status.value}")

            try:
                # Get processor for this status
                processor_func = self.status_processors[status]

                # Process tasks for this status
                status_result = processor_func()
                overall_results["status_results"][status.value] = status_result

                # Update overall success
                if not status_result.get("success", False):
                    overall_results["overall_success"] = False

                # Update statistics
                status_stats = status_result.get("stats", {})
                self.stats["by_status"][status.value] = status_stats

                logger.info(f"✅ Status {status.value} processed: {status_stats}")

            except Exception as e:
                logger.error(f"❌ Error processing status {status.value}: {e}")
                overall_results["status_results"][status.value] = {
                    "success": False,
                    "error": str(e),
                    "stats": {"processed": 0, "successful": 0, "failed": 1},
                }
                overall_results["overall_success"] = False

        # Compile overall statistics
        self._compile_overall_stats(overall_results)

        logger.info("🏁 Multi-status processing completed")
        logger.info(f"📊 Overall success: {overall_results['overall_success']}")

        return overall_results

    def process_single_status(self, status: TaskStatus) -> Dict[str, Any]:
        """
        Process tasks for a single status.

        Args:
            status: TaskStatus to process

        Returns:
            Dictionary with processing results
        """
        logger.info(f"🎯 Processing single status: {status.value}")

        if status not in self.status_processors:
            logger.error(f"❌ No processor configured for status: {status.value}")
            return {
                "success": False,
                "error": f"No processor for status {status.value}",
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

        try:
            processor_func = self.status_processors[status]
            result = processor_func()

            self.stats["by_status"][status.value] = result.get("stats", {})

            return result

        except Exception as e:
            logger.error(f"❌ Error processing status {status.value}: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

    def _process_refine_tasks(self) -> Dict[str, Any]:
        """Process tasks with 'To Refine' status."""
        logger.info("🔍 Processing 'To Refine' tasks...")

        try:
            # Get tasks to refine
            tasks = self.db_ops.get_tasks_to_refine()

            if not tasks:
                logger.info("ℹ️  No tasks found with 'To Refine' status")
                return {
                    "success": True,
                    "message": "No tasks to refine",
                    "stats": {"processed": 0, "successful": 0, "failed": 0},
                }

            logger.info(f"📋 Found {len(tasks)} tasks to refine")

            # Process tasks using content processor
            successful = 0
            failed = 0

            for task in tasks:
                try:
                    # Process task using content processor
                    result = self.content_processor.process_task(task, lambda: False)

                    if result.get("status") == "completed":
                        successful += 1
                        task_id = task.get("id", "unknown")
                        logger.info(f"✅ Refined task: {task_id}")

                        # Track this task to prevent immediate reprocessing when it moves to REFINED status
                        self._last_process_time[task_id] = time.time()
                        self._recently_processed_tasks.add(task_id)
                    else:
                        failed += 1
                        logger.error(f"❌ Failed to refine task: {task.get('id', 'unknown')}")

                except Exception as e:
                    failed += 1
                    logger.error(f"❌ Error refining task {task.get('id', 'unknown')}: {e}")

            return {
                "success": successful > 0,
                "message": f"Processed {len(tasks)} refine tasks",
                "stats": {"processed": len(tasks), "successful": successful, "failed": failed},
            }

        except Exception as e:
            logger.error(f"❌ Error processing refine tasks: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

    def _process_prepare_tasks(self) -> Dict[str, Any]:
        """Process tasks with 'Prepare Tasks' status."""
        logger.info("🔧 Processing 'Prepare Tasks' tasks...")

        try:
            # Get tasks with 'Prepare Tasks' status
            prepare_tasks_pages = self.notion_client.query_tickets_by_status("Prepare Tasks")

            if not prepare_tasks_pages:
                logger.info("ℹ️  No tasks found with 'Prepare Tasks' status")
                return {
                    "success": True,
                    "message": "No tasks to prepare",
                    "stats": {"processed": 0, "successful": 0, "failed": 0},
                }

            logger.info(f"📋 Found {len(prepare_tasks_pages)} tasks to prepare")

            # Extract ticket IDs
            ticket_ids = self.notion_client.extract_ticket_ids(prepare_tasks_pages)

            # Validate files exist
            valid_ticket_ids = self.file_ops.validate_task_files(ticket_ids)

            if not valid_ticket_ids:
                logger.warning("⚠️ No valid ticket files found")
                return {
                    "success": False,
                    "message": "No valid files to prepare",
                    "stats": {
                        "processed": len(ticket_ids),
                        "successful": 0,
                        "failed": len(ticket_ids),
                    },
                }

            # IMPORTANT: Process only one ticket at a time to avoid tasks.json conflicts
            if len(valid_ticket_ids) > 1:
                logger.info(f"📝 Found {len(valid_ticket_ids)} valid tickets. Processing only the first one to avoid tasks.json conflicts.")
                logger.info(f"🔄 Remaining tickets will be processed in subsequent runs: {valid_ticket_ids[1:]}")
                valid_ticket_ids = [valid_ticket_ids[0]]  # Process only the first ticket

            # Update status to 'Preparing Tasks' (only for selected ticket)
            page_ids = [page["id"] for page in prepare_tasks_pages if self.notion_client.extract_ticket_ids([page])[0] in valid_ticket_ids]

            self.notion_client.update_tickets_status_batch(page_ids, "Preparing Tasks")

            # Execute task-master commands
            command_results = self.cmd_executor.execute_taskmaster_command(valid_ticket_ids)
            successful_ticket_ids = [item["ticket_id"] for item in command_results["successful_executions"]]

            # Copy tasks.json files
            taskmaster_tasks_path = os.path.join(self.project_root, ".taskmaster", "tasks", "tasks.json")
            tasks_dest_dir = os.path.join(get_tasks_dir(), "tasks")
            copy_results = self.file_ops.copy_tasks_file(successful_ticket_ids, source_path=taskmaster_tasks_path, dest_dir=tasks_dest_dir)

            # Upload JSON files to Notion pages
            upload_data = []
            for page in prepare_tasks_pages:
                page_ticket_ids = self.notion_client.extract_ticket_ids([page])
                if page_ticket_ids and page_ticket_ids[0] in successful_ticket_ids:
                    # Get the full ticket ID format for the file path
                    ticket_id = page_ticket_ids[0]
                    full_ticket_id = self.file_ops._get_full_ticket_id(ticket_id)
                    upload_data.append(
                        {
                            "ticket_id": ticket_id,
                            "page_id": page["id"],
                            "tasks_file_path": os.path.join(get_tasks_dir(), "tasks", f"{full_ticket_id}.json"),
                        }
                    )

            upload_results = self.notion_client.upload_tasks_files_to_pages(upload_data)

            # Finalize status to 'Ready to Run' for successfully uploaded tasks
            successful_upload_page_ids = [item["page_id"] for item in upload_results["successful_uploads"]]

            finalized_count = 0
            if successful_upload_page_ids:
                finalize_results = self.notion_client.update_tickets_status_batch(successful_upload_page_ids, "Ready to run")
                finalized_count = finalize_results.get("success_count", 0)
                logger.info(f"✅ Finalized {finalized_count} tasks to 'Ready to run' status")

            # Handle failed tasks - mark them as Failed for valid status transition
            failed_ticket_ids = [item["ticket_id"] for item in command_results["failed_executions"]]
            if failed_ticket_ids:
                failed_page_ids = []
                for page in prepare_tasks_pages:
                    page_ticket_ids = self.notion_client.extract_ticket_ids([page])
                    if page_ticket_ids and page_ticket_ids[0] in failed_ticket_ids:
                        failed_page_ids.append(page["id"])

                if failed_page_ids:
                    self.notion_client.update_tickets_status_batch(failed_page_ids, "Failed")
                    logger.info(f"❌ Marked {len(failed_page_ids)} failed tasks as 'Failed'")

            return {
                "success": finalized_count > 0,
                "message": f"Prepared and finalized {finalized_count} tasks to 'Ready to run'",
                "stats": {
                    "processed": len(valid_ticket_ids),
                    "successful": finalized_count,
                    "failed": len(valid_ticket_ids) - finalized_count,
                },
            }

        except Exception as e:
            logger.error(f"❌ Error processing prepare tasks: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

    def _process_preparing_tasks(self) -> Dict[str, Any]:
        """Process tasks with 'Preparing Tasks' status by checking for completion and transitioning to 'Ready to Run'."""
        logger.info("⏳ Processing 'Preparing Tasks' tasks...")

        try:
            # Get tasks with 'Preparing Tasks' status
            tasks = self.db_ops.get_task_by_status(TaskStatus.PREPARING_TASKS)

            if not tasks:
                logger.info("ℹ️  No tasks found with 'Preparing Tasks' status")
                return {
                    "success": True,
                    "message": "No preparing tasks found",
                    "stats": {"processed": 0, "successful": 0, "failed": 0},
                }

            logger.info(f"📋 Found {len(tasks)} preparing tasks")

            # Check each task to see if task generation is complete
            completed_tasks = []
            still_preparing_tasks = []
            failed_tasks = []

            for task in tasks:
                try:
                    task_id = task.get("id", "unknown")
                    logger.info(f"🔍 Checking completion status for task: {task_id}")

                    # Check if this task has completed preparation by looking for generated JSON files
                    if self._is_task_preparation_complete(task):
                        logger.info(f"✅ Task {task_id} preparation is complete - ready to transition")
                        completed_tasks.append(task)
                    else:
                        logger.info(f"⏳ Task {task_id} is still being prepared")
                        still_preparing_tasks.append(task)

                except Exception as e:
                    logger.error(f"❌ Error checking task {task.get('id', 'unknown')}: {e}")
                    failed_tasks.append(task)

            # Transition completed tasks to 'Ready to Run'
            successful_transitions = 0
            failed_transitions = 0

            for task in completed_tasks:
                try:
                    task_id = task.get("id", "unknown")

                    # Use safe status transition to handle race conditions
                    result = self._safe_status_transition(
                        task_id=task_id,
                        expected_from_status=TaskStatus.PREPARING_TASKS.value,
                        to_status=TaskStatus.READY_TO_RUN.value,
                        task_description="preparing",
                    )

                    if result["success"]:
                        successful_transitions += 1
                    else:
                        failed_transitions += 1

                except Exception as e:
                    failed_transitions += 1
                    logger.error(f"❌ Error transitioning task {task.get('id', 'unknown')}: {e}")

            # Log summary
            total_tasks = len(tasks)
            logger.info(f"📊 Task preparation summary:")
            logger.info(f"   📋 Total tasks checked: {total_tasks}")
            logger.info(f"   ✅ Completed and transitioned: {successful_transitions}")
            logger.info(f"   ⏳ Still preparing: {len(still_preparing_tasks)}")
            logger.info(f"   ❌ Failed transitions: {failed_transitions}")
            logger.info(f"   🚫 Check failures: {len(failed_tasks)}")

            return {
                "success": successful_transitions > 0 or len(still_preparing_tasks) > 0,
                "message": f"Processed {total_tasks} preparing tasks, {successful_transitions} transitioned to Ready to Run",
                "stats": {
                    "processed": total_tasks,
                    "successful": successful_transitions + len(still_preparing_tasks),  # Still preparing is not a failure
                    "failed": failed_transitions + len(failed_tasks),
                },
                "details": {
                    "completed_and_transitioned": successful_transitions,
                    "still_preparing": len(still_preparing_tasks),
                    "failed_transitions": failed_transitions,
                    "check_failures": len(failed_tasks),
                },
            }

        except Exception as e:
            logger.error(f"❌ Error processing preparing tasks: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

    def _is_task_preparation_complete(self, task: Dict[str, Any]) -> bool:
        """
        Check if task preparation is complete by verifying that generated JSON files exist
        and the taskmaster process has finished.

        Args:
            task: Task dictionary from Notion

        Returns:
            bool: True if preparation is complete, False otherwise
        """
        try:
            task_id = task.get("id", "unknown")

            # First, we need to get the ticket ID associated with this task
            # We'll need to check if the JSON file exists in the expected location

            # Check if there's a corresponding generated tasks JSON file
            tasks_dest_dir = os.path.join(get_tasks_dir(), "tasks")

            # Try to find a JSON file for this task ID
            # The file might be named after the ticket ID format
            potential_files = []

            if os.path.exists(tasks_dest_dir):
                # Look for any JSON files that might correspond to this task
                for filename in os.listdir(tasks_dest_dir):
                    if filename.endswith(".json"):
                        file_path = os.path.join(tasks_dest_dir, filename)

                        # Check if this JSON file contains our task ID or references it
                        try:
                            with open(file_path, "r") as f:
                                file_content = f.read()
                                # Simple check - if the task_id appears in the file, it might be related
                                if task_id in file_content:
                                    potential_files.append(file_path)
                        except Exception as e:
                            logger.debug(f"Could not read {file_path}: {e}")
                            continue

            # If we found potential files, check if they contain valid task structures
            if potential_files:
                logger.info(f"🔍 Found {len(potential_files)} potential JSON files for task {task_id}")

                for file_path in potential_files:
                    try:
                        with open(file_path, "r") as f:
                            json_data = json.load(f)

                        # Check if the JSON has the expected structure with tasks
                        if isinstance(json_data, dict) and "master" in json_data:
                            master_data = json_data["master"]
                            if "tasks" in master_data and isinstance(master_data["tasks"], list):
                                # Check if there are actual tasks with meaningful content
                                tasks_list = master_data["tasks"]
                                if len(tasks_list) > 0:
                                    # Check if tasks have proper structure
                                    first_task = tasks_list[0]
                                    if all(key in first_task for key in ["id", "title", "description"]):
                                        logger.info(f"✅ Task {task_id} has valid generated JSON with {len(tasks_list)} tasks")
                                        return True

                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        logger.debug(f"JSON file {file_path} is not valid or incomplete: {e}")
                        continue

            # Alternative approach: Check if the .taskmaster/tasks/tasks.json file exists and has been recently updated
            taskmaster_tasks_path = os.path.join(self.project_root, ".taskmaster", "tasks", "tasks.json")

            if os.path.exists(taskmaster_tasks_path):
                try:
                    # Check if the file was modified recently (within last 10 minutes)
                    file_mtime = os.path.getmtime(taskmaster_tasks_path)
                    current_time = time.time()

                    # If file was modified within last 10 minutes, check its content
                    if current_time - file_mtime < 600:  # 10 minutes
                        with open(taskmaster_tasks_path, "r") as f:
                            json_data = json.load(f)

                        # Check if there are actual tasks generated
                        if isinstance(json_data, dict) and "master" in json_data:
                            master_data = json_data["master"]
                            if "tasks" in master_data and isinstance(master_data["tasks"], list):
                                tasks_list = master_data["tasks"]
                                if len(tasks_list) > 0:
                                    logger.info(f"✅ Task {task_id} preparation likely complete - taskmaster generated {len(tasks_list)} tasks recently")
                                    return True

                except Exception as e:
                    logger.debug(f"Could not check taskmaster tasks.json: {e}")

            logger.info(f"⏳ Task {task_id} preparation still in progress - no valid generated files found")
            return False

        except Exception as e:
            logger.error(f"❌ Error checking task preparation completion for {task.get('id', 'unknown')}: {e}")
            # If we can't determine, assume it's still preparing to be safe
            return False

    def _process_queued_tasks(self) -> Dict[str, Any]:
        """Process tasks with 'Queued to run' status using existing processor."""
        logger.info("🚀 Processing 'Queued to run' tasks...")

        try:
            # Use the existing simple queued processor
            success = self.simple_queued_processor.process_queued_tasks()

            # Get queue depth for statistics
            queue_depth = self.db_ops.get_queue_depth()

            return {
                "success": success,
                "message": f"Queued processing {'completed' if success else 'failed'}",
                "stats": {
                    "processed": 1 if queue_depth > 0 else 0,
                    "successful": 1 if success else 0,
                    "failed": 0 if success else (1 if queue_depth > 0 else 0),
                },
            }

        except Exception as e:
            logger.error(f"❌ Error processing queued tasks: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

    def _process_failed_tasks(self) -> Dict[str, Any]:
        """Process tasks with 'Failed' status for potential retry."""
        logger.info("🔄 Processing 'Failed' tasks...")

        try:
            # Get failed tasks
            failed_tasks = self.db_ops.get_task_by_status(TaskStatus.FAILED)

            if not failed_tasks:
                logger.info("ℹ️  No tasks found with 'Failed' status")
                return {
                    "success": True,
                    "message": "No failed tasks found",
                    "stats": {"processed": 0, "successful": 0, "failed": 0},
                }

            logger.info(f"📋 Found {len(failed_tasks)} failed tasks")

            # For now, just log failed tasks. In the future, we could implement retry logic
            successful_retries = 0

            for task in failed_tasks:
                task_id = task.get("id", "unknown")
                logger.info(f"🔍 Failed task found: {task_id}")

                # Could implement retry logic here based on failure reason, age, etc.
                # For now, just count them

            logger.info(f"ℹ️  Found {len(failed_tasks)} failed tasks - retry logic not yet implemented")

            return {
                "success": True,
                "message": f"Analyzed {len(failed_tasks)} failed tasks",
                "stats": {
                    "processed": len(failed_tasks),
                    "successful": successful_retries,
                    "failed": len(failed_tasks) - successful_retries,
                },
            }

        except Exception as e:
            logger.error(f"❌ Error processing failed tasks: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

    def _process_refined_tasks(self) -> Dict[str, Any]:
        """Process tasks with 'Refined' status by triggering prepare workflow."""
        logger.info("🔧 Processing 'Refined' tasks (equivalent to --prepare)...")

        try:
            # Get tasks with 'Refined' status
            refined_tasks = self.db_ops.get_task_by_status(TaskStatus.REFINED)

            # Filter out recently processed tasks to avoid immediate reprocessing
            current_time = time.time()
            cooldown_period = 120  # 2 minutes cooldown

            # Clean up old tracking entries (older than 1 hour)
            cleanup_threshold = current_time - 3600  # 1 hour
            expired_task_ids = [task_id for task_id, last_time in self._last_process_time.items() if last_time < cleanup_threshold]
            for task_id in expired_task_ids:
                self._last_process_time.pop(task_id, None)
                self._recently_processed_tasks.discard(task_id)

            if expired_task_ids:
                logger.debug(f"🧹 Cleaned up {len(expired_task_ids)} expired task tracking entries")

            filtered_tasks = []
            for task in refined_tasks:
                task_id = task.get("id", "unknown")
                last_processed = self._last_process_time.get(task_id, 0)

                if current_time - last_processed > cooldown_period:
                    filtered_tasks.append(task)
                else:
                    remaining_cooldown = int(cooldown_period - (current_time - last_processed))
                    logger.info(f"⏳ Skipping recently processed task {task_id} (cooldown: {remaining_cooldown}s remaining)")

            refined_tasks = filtered_tasks

            if not refined_tasks:
                original_count = len(self.db_ops.get_task_by_status(TaskStatus.REFINED))
                if original_count > 0:
                    logger.info(f"ℹ️  Found {original_count} refined tasks, but all are in cooldown period")
                else:
                    logger.info("ℹ️  No tasks found with 'Refined' status")
                return {
                    "success": True,
                    "message": ("No refined tasks to process (all in cooldown)" if original_count > 0 else "No refined tasks found"),
                    "stats": {"processed": 0, "successful": 0, "failed": 0},
                }

            logger.info(f"📋 Found {len(refined_tasks)} refined tasks")

            # For refined tasks, we need to run the equivalent of --prepare mode
            # This involves changing their status to 'Prepare Tasks' first, then processing

            successful_tasks = 0
            failed_tasks = 0

            for task in refined_tasks:
                try:
                    task_id = task.get("id", "unknown")

                    # Use safe status transition to handle race conditions
                    result = self._safe_status_transition(
                        task_id=task_id,
                        expected_from_status=TaskStatus.REFINED.value,
                        to_status=TaskStatus.PREPARE_TASKS.value,
                        task_description="refined",
                    )

                    if result["success"]:
                        # Now trigger the prepare workflow by calling the prepare processor
                        # But we need to wait a moment for the status change to propagate
                        time.sleep(1)
                        successful_tasks += 1

                        # Track this task to prevent immediate reprocessing
                        self._last_process_time[task_id] = time.time()
                        self._recently_processed_tasks.add(task_id)
                    else:
                        failed_tasks += 1

                except Exception as e:
                    failed_tasks += 1
                    logger.error(f"❌ Error processing refined task {task.get('id', 'unknown')}: {e}")

            # After transitioning refined tasks to prepare tasks, run the prepare processor
            if successful_tasks > 0:
                logger.info(f"🚀 Now running prepare workflow for {successful_tasks} transitioned tasks...")
                prepare_result = self._process_prepare_tasks()

                # Combine results
                return {
                    "success": prepare_result.get("success", False) and successful_tasks > 0,
                    "message": f"Processed {len(refined_tasks)} refined tasks, {successful_tasks} successful transitions",
                    "stats": {
                        "processed": len(refined_tasks),
                        "successful": (successful_tasks if prepare_result.get("success", False) else 0),
                        "failed": failed_tasks + (0 if prepare_result.get("success", False) else successful_tasks),
                    },
                    "prepare_workflow_result": prepare_result,
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to transition any refined tasks",
                    "stats": {
                        "processed": len(refined_tasks),
                        "successful": 0,
                        "failed": failed_tasks,
                    },
                }

        except Exception as e:
            logger.error(f"❌ Error processing refined tasks: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

    def _process_ready_to_run_tasks(self) -> Dict[str, Any]:
        """Process tasks with 'Ready to Run' status by transitioning them to 'Queued to run'."""
        logger.info("🚀 Processing 'Ready to Run' tasks...")

        try:
            # Get tasks with 'Ready to Run' status
            ready_tasks = self.db_ops.get_task_by_status(TaskStatus.READY_TO_RUN)

            if not ready_tasks:
                logger.info("ℹ️  No tasks found with 'Ready to Run' status")
                return {
                    "success": True,
                    "message": "No ready to run tasks found",
                    "stats": {"processed": 0, "successful": 0, "failed": 0},
                }

            logger.info(f"📋 Found {len(ready_tasks)} ready to run tasks")

            successful_transitions = 0
            failed_transitions = 0

            for task in ready_tasks:
                try:
                    task_id = task.get("id", "unknown")

                    # Use safe status transition to handle race conditions
                    result = self._safe_status_transition(
                        task_id=task_id,
                        expected_from_status=TaskStatus.READY_TO_RUN.value,
                        to_status=TaskStatus.QUEUED_TO_RUN.value,
                        task_description="ready",
                    )

                    if result["success"]:
                        successful_transitions += 1
                    else:
                        failed_transitions += 1

                except Exception as e:
                    failed_transitions += 1
                    logger.error(f"❌ Error processing ready task {task.get('id', 'unknown')}: {e}")

            return {
                "success": successful_transitions > 0,
                "message": f"Processed {len(ready_tasks)} ready tasks, {successful_transitions} successfully queued",
                "stats": {
                    "processed": len(ready_tasks),
                    "successful": successful_transitions,
                    "failed": failed_transitions,
                },
            }

        except Exception as e:
            logger.error(f"❌ Error processing ready to run tasks: {e}")
            return {
                "success": False,
                "error": str(e),
                "stats": {"processed": 0, "successful": 0, "failed": 1},
            }

    def _compile_overall_stats(self, results: Dict[str, Any]):
        """Compile overall statistics from individual status results."""
        total_processed = 0
        total_successful = 0
        total_failed = 0

        for status_value, status_result in results["status_results"].items():
            stats = status_result.get("stats", {})
            total_processed += stats.get("processed", 0)
            total_successful += stats.get("successful", 0)
            total_failed += stats.get("failed", 0)

        # Update instance stats
        self.stats["total_processed"] = total_processed
        self.stats["successful"] = total_successful
        self.stats["failed"] = total_failed

        # Add to results
        results["summary"] = {
            "total_processed": total_processed,
            "successful": total_successful,
            "failed": total_failed,
            "success_rate": ((total_successful / total_processed * 100) if total_processed > 0 else 0.0),
        }

        logger.info(f"📊 Overall Statistics:")
        logger.info(f"   📋 Total processed: {total_processed}")
        logger.info(f"   ✅ Successful: {total_successful}")
        logger.info(f"   ❌ Failed: {total_failed}")
        logger.info(f"   📊 Success rate: {results['summary']['success_rate']:.1f}%")

    def _get_empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "status_results": {},
            "overall_success": True,
            "summary": {"total_processed": 0, "successful": 0, "failed": 0, "success_rate": 0.0},
        }

    def get_status_distribution(self) -> Dict[str, int]:
        """Get current distribution of tasks across all statuses."""
        return self.db_ops.get_status_distribution()

    def get_processing_recommendations(self) -> Dict[str, Any]:
        """Get recommendations for which statuses to process based on current state."""
        distribution = self.get_status_distribution()

        recommendations = {
            "priority_statuses": [],
            "optional_statuses": [],
            "skip_statuses": [],
            "distribution": distribution,
        }

        # Prioritize statuses with tasks
        for status in TaskStatus:
            count = distribution.get(status.value, 0)

            if count > 0:
                if status in [TaskStatus.FAILED, TaskStatus.QUEUED_TO_RUN, TaskStatus.READY_TO_RUN]:
                    recommendations["priority_statuses"].append(
                        {
                            "status": status.value,
                            "count": count,
                            "reason": "High priority - needs immediate attention",
                        }
                    )
                elif status in [
                    TaskStatus.TO_REFINE,
                    TaskStatus.PREPARE_TASKS,
                    TaskStatus.PREPARING_TASKS,
                ]:
                    recommendations["priority_statuses"].append(
                        {
                            "status": status.value,
                            "count": count,
                            "reason": ("Ready for processing" if status != TaskStatus.PREPARING_TASKS else "Needs completion check"),
                        }
                    )
                elif status == TaskStatus.REFINED:
                    # Refined tasks should be processed to move to next workflow stage
                    # but with logic to prevent immediate reprocessing of the same task
                    recommendations["priority_statuses"].append(
                        {
                            "status": status.value,
                            "count": count,
                            "reason": "Ready for workflow progression",
                        }
                    )
                else:
                    recommendations["optional_statuses"].append({"status": status.value, "count": count, "reason": "Standard processing"})
            else:
                recommendations["skip_statuses"].append({"status": status.value, "count": count, "reason": "No tasks in this status"})

        return recommendations


def main():
    """Main entry point for multi-status processing."""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-status task processor")
    parser.add_argument("--project-root", default="/Users/damian/Web/ddcode/nomad", help="Project root directory")
    parser.add_argument("--status", choices=[s.value for s in TaskStatus], help="Process only this specific status")
    parser.add_argument(
        "--include",
        nargs="+",
        choices=[s.value for s in TaskStatus],
        help="Include only these statuses",
    )
    parser.add_argument("--exclude", nargs="+", choices=[s.value for s in TaskStatus], help="Exclude these statuses")
    parser.add_argument("--recommendations", action="store_true", help="Show processing recommendations and exit")

    args = parser.parse_args()

    # Initialize processor
    processor = MultiStatusProcessor(args.project_root)

    # Show recommendations if requested
    if args.recommendations:
        recommendations = processor.get_processing_recommendations()
        print("\n📊 Current Status Distribution:")
        for status, count in recommendations["distribution"].items():
            print(f"   {status}: {count}")

        print("\n🎯 Priority Statuses:")
        for item in recommendations["priority_statuses"]:
            print(f"   {item['status']} ({item['count']}) - {item['reason']}")

        print("\n📋 Optional Statuses:")
        for item in recommendations["optional_statuses"]:
            print(f"   {item['status']} ({item['count']}) - {item['reason']}")

        sys.exit(0)

    # Process tasks
    if args.status:
        # Process single status
        status = TaskStatus(args.status)
        result = processor.process_single_status(status)
        success = result.get("success", False)
    else:
        # Process multiple statuses
        include_statuses = {TaskStatus(s) for s in args.include} if args.include else None
        exclude_statuses = {TaskStatus(s) for s in args.exclude} if args.exclude else None

        result = processor.process_all_statuses(include_statuses=include_statuses, exclude_statuses=exclude_statuses)
        success = result.get("overall_success", False)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
