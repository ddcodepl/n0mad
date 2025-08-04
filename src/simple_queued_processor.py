#!/usr/bin/env python3
"""
Simple queued task processor that implements the new logic:
1. Check for records with 'Queued' status
2. Take the first record and get its ID
3. Look for TASK_DIR/tasks/<TASK_ID>.json file
4. Replace ~/.taskmaster/tasks/tasks.json with the found file
5. Update status to 'In progress'
6. Execute Claude Code command to process all tasks
7. Update status to 'Done' or 'Failed' based on results
"""

import os
import sys
import json
import shutil
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from database_operations import DatabaseOperations
from notion_wrapper import NotionClientWrapper
from status_transition_manager import StatusTransitionManager
from task_status import TaskStatus
from logging_config import get_logger

logger = get_logger(__name__)


class SimpleQueuedProcessor:
    """Simple processor for handling queued tasks with the new logic."""
    
    def __init__(self, project_root: str):
        """
        Initialize the simple queued processor.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.task_dir = self.project_root / "src" / "tasks" / "tasks"
        self.taskmaster_tasks_file = self.project_root / ".taskmaster" / "tasks" / "tasks.json"
        
        # Initialize components
        self.notion_client = NotionClientWrapper()
        self.db_ops = DatabaseOperations(self.notion_client)
        self.status_manager = StatusTransitionManager(self.notion_client)
        
        # Ensure critical directories exist
        self.taskmaster_tasks_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎯 SimpleQueuedProcessor initialized")
        logger.info(f"   📁 Task directory: {self.task_dir}")
        logger.info(f"   📋 TaskMaster file: {self.taskmaster_tasks_file}")
    
    def process_queued_tasks(self) -> bool:
        """
        Process queued tasks using the new simplified logic.
        
        Returns:
            True if processing was successful, False otherwise
        """
        logger.info("🚀 Starting simple queued task processing...")
        
        try:
            # Step 1: Check for queued tasks
            queued_tasks = self._get_queued_tasks()
            if not queued_tasks:
                logger.info("ℹ️  No tasks with 'Queued to run' status found")
                return True
            
            # Step 2: Process tasks one by one (ensuring max 1 in progress)
            success_count = 0
            total_tasks = len(queued_tasks)
            
            for i, task in enumerate(queued_tasks, 1):
                logger.info(f"📋 Processing task {i}/{total_tasks}: {task.get('title', 'Unknown')}")
                
                if self._process_single_task(task):
                    success_count += 1
                    logger.info(f"✅ Task {i}/{total_tasks} completed successfully")
                else:
                    logger.error(f"❌ Task {i}/{total_tasks} failed")
                
                # Add small delay between tasks to prevent overwhelming the system
                if i < total_tasks:
                    time.sleep(2)
            
            logger.info(f"🏁 Queued task processing completed: {success_count}/{total_tasks} successful")
            return success_count == total_tasks
            
        except Exception as e:
            logger.error(f"❌ Queued task processing failed: {e}")
            return False
    
    def _get_queued_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks with 'Queued to run' status."""
        try:
            queued_tasks = self.db_ops.get_queued_tasks()
            logger.info(f"🔍 Found {len(queued_tasks)} queued tasks")
            return queued_tasks
        except Exception as e:
            logger.error(f"❌ Failed to get queued tasks: {e}")
            return []
    
    def _validate_task(self, task: Dict[str, Any]) -> bool:
        """
        Validate task has required fields.
        
        Args:
            task: Task dictionary from Notion
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(task, dict):
            logger.error("❌ Task is not a dictionary")
            return False
        
        required_fields = ["id", "ticket_id", "title"]
        for field in required_fields:
            if not task.get(field):
                logger.error(f"❌ Task missing required field: {field}")
                return False
        
        return True
    
    def _ensure_max_one_in_progress(self) -> bool:
        """
        Ensure no more than 1 task is currently in progress.
        
        Returns:
            True if safe to proceed, False if another task is in progress
        """
        try:
            in_progress_tasks = self.db_ops.get_task_by_status(TaskStatus.IN_PROGRESS)
            
            if len(in_progress_tasks) > 0:
                logger.warning(f"⚠️ Found {len(in_progress_tasks)} tasks already in progress")
                logger.info("⏳ Waiting for current tasks to complete before processing new ones")
                return False
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to check in-progress tasks: {e}")
            return False
    
    def _process_single_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a single queued task.
        
        Args:
            task: Task dictionary from Notion
            
        Returns:
            True if successful, False otherwise
        """
        # Validate task data
        if not self._validate_task(task):
            return False
        
        # Ensure max one task in progress
        if not self._ensure_max_one_in_progress():
            logger.info("⏭️ Skipping task processing - another task is in progress")
            return False
        
        page_id = task.get("id")
        ticket_id = task.get("ticket_id")
        title = task.get("title", "Unknown")
        
        logger.info(f"🎯 Processing task: {title} (Ticket: {ticket_id})")
        
        try:
            # Step 1: Update status to 'In progress'
            transition = self.status_manager.transition_status(
                page_id=page_id,
                from_status=TaskStatus.QUEUED_TO_RUN.value,
                to_status=TaskStatus.IN_PROGRESS.value
            )
            
            if transition.result.value != "success":
                logger.error(f"❌ Failed to update status to 'In progress': {transition.error}")
                return False
            
            logger.info(f"✅ Status updated to 'In progress' for task {ticket_id}")
            
            # Step 2: Look for task file
            task_file = self._find_task_file(ticket_id)
            if not task_file:
                self._update_status_to_failed(page_id, f"Task file not found for {ticket_id}")
                return False
            
            # Step 3: Copy task file to taskmaster location
            if not self._copy_task_file(task_file):
                self._update_status_to_failed(page_id, f"Failed to copy task file {task_file}")
                return False
            
            # Step 4: Execute Claude Code command
            claude_success = self._execute_claude_command()
            
            # Step 5: Update final status
            if claude_success:
                final_transition = self.status_manager.transition_status(
                    page_id=page_id,
                    from_status=TaskStatus.IN_PROGRESS.value,
                    to_status=TaskStatus.DONE.value
                )
                
                if final_transition.result.value == "success":
                    logger.info(f"✅ Task {ticket_id} completed successfully")
                    return True
                else:
                    logger.error(f"❌ Failed to update final status to 'Done': {final_transition.error}")
                    return False
            else:
                self._update_status_to_failed(page_id, "Claude Code execution failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error processing task {ticket_id}: {e}")
            try:
                self._update_status_to_failed(page_id, f"Processing error: {str(e)}")
            except Exception as status_error:
                logger.error(f"❌ Failed to update status to failed: {status_error}")
            return False
    
    def _find_task_file(self, ticket_id: str) -> Optional[Path]:
        """
        Find the task file for the given ticket ID.
        
        Args:
            ticket_id: Ticket ID to look for
            
        Returns:
            Path to the task file if found, None otherwise
        """
        # Try exact match first
        exact_file = self.task_dir / f"{ticket_id}.json"
        if exact_file.exists():
            logger.info(f"📄 Found exact task file: {exact_file}")
            return exact_file
        
        # Try with different formats (NOMAD-XX, etc.)
        for task_file in self.task_dir.glob("*.json"):
            if ticket_id in task_file.stem:
                logger.info(f"📄 Found matching task file: {task_file}")
                return task_file
        
        logger.error(f"❌ Task file not found for ticket ID: {ticket_id}")
        logger.info(f"🔍 Available files in {self.task_dir}:")
        for task_file in self.task_dir.glob("*.json"):
            logger.info(f"   📄 {task_file.name}")
        
        return None
    
    def _copy_task_file(self, source_file: Path) -> bool:
        """
        Copy task file to taskmaster location.
        
        Args:
            source_file: Source task file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create backup if target exists
            if self.taskmaster_tasks_file.exists():
                backup_file = self.taskmaster_tasks_file.with_suffix(
                    f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                shutil.copy2(self.taskmaster_tasks_file, backup_file)
                logger.info(f"📋 Created backup: {backup_file}")
            
            # Copy source file to target location
            shutil.copy2(source_file, self.taskmaster_tasks_file)
            logger.info(f"✅ Copied {source_file} to {self.taskmaster_tasks_file}")
            
            # Verify the copy was successful
            if not self.taskmaster_tasks_file.exists():
                logger.error("❌ Task file copy verification failed")
                return False
            
            # Verify it's valid JSON
            try:
                with open(self.taskmaster_tasks_file, 'r') as f:
                    json.load(f)
                logger.info("✅ Task file copy verified as valid JSON")
                return True
            except json.JSONDecodeError as e:
                logger.error(f"❌ Copied task file is not valid JSON: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to copy task file: {e}")
            return False
    
    def _execute_claude_command(self) -> bool:
        """
        Execute Claude Code command to process all tasks.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🤖 Executing Claude Code command...")
            
            # Change to project root directory for Claude Code execution
            original_cwd = os.getcwd()
            os.chdir(self.project_root)
            
            try:
                # Execute Claude Code with the predefined prompt
                # Using headless mode to avoid interactive prompts
                prompt = "Process all tasks from the task master, don't stop unless you finish all of the tasks, after that close the app."
                
                cmd = ["claude", "-p", prompt]
                
                logger.info(f"🚀 Running command: {' '.join(cmd)}")
                
                # Execute with timeout to prevent hanging
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600,  # 1 hour timeout
                    cwd=self.project_root
                )
                
                logger.info(f"📊 Claude Code exit code: {result.returncode}")
                
                if result.stdout:
                    logger.info("📋 Claude Code stdout:")
                    for line in result.stdout.split('\n')[:10]:  # Log first 10 lines
                        if line.strip():
                            logger.info(f"   {line}")
                
                if result.stderr:
                    logger.warning("⚠️ Claude Code stderr:")
                    for line in result.stderr.split('\n')[:10]:  # Log first 10 lines
                        if line.strip():
                            logger.warning(f"   {line}")
                
                # Consider exit code 0 as success
                success = result.returncode == 0
                
                if success:
                    logger.info("✅ Claude Code execution completed successfully")
                else:
                    logger.error(f"❌ Claude Code execution failed with exit code {result.returncode}")
                
                return success
                
            finally:
                # Always restore original working directory
                os.chdir(original_cwd)
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Claude Code execution timed out after 1 hour")
            return False
        except FileNotFoundError:
            logger.error("❌ Claude Code command not found. Make sure 'claude' is installed and in PATH")
            return False
        except Exception as e:
            logger.error(f"❌ Claude Code execution failed: {e}")
            return False
    
    def _update_status_to_failed(self, page_id: str, error_message: str):
        """
        Update task status to Failed with error message.
        
        Args:
            page_id: Notion page ID
            error_message: Error message to include
        """
        try:
            transition = self.status_manager.transition_status(
                page_id=page_id,
                from_status=TaskStatus.IN_PROGRESS.value,
                to_status=TaskStatus.FAILED.value,
                validate_transition=False  # Allow from any status in error scenarios
            )
            
            if transition.result.value == "success":
                logger.info(f"✅ Status updated to 'Failed' with message: {error_message}")
                
                # Try to update feedback with error message
                try:
                    self.notion_client.update_page_property(
                        page_id=page_id,
                        property_name="Feedback",
                        property_value=f"[{datetime.now().isoformat()}] FAILED: {error_message}"
                    )
                except Exception as feedback_error:
                    logger.warning(f"⚠️ Failed to update feedback property: {feedback_error}")
            else:
                logger.error(f"❌ Failed to update status to 'Failed': {transition.error}")
                
        except Exception as e:
            logger.error(f"❌ Error updating status to failed: {e}")


def main():
    """Main entry point for simple queued processing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple queued task processor")
    parser.add_argument(
        "--project-root",
        default="/Users/damian/Web/ddcode/nomad",
        help="Project root directory (default: current directory's parent)"
    )
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = SimpleQueuedProcessor(args.project_root)
    
    # Process queued tasks
    success = processor.process_queued_tasks()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()