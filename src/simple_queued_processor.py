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
import hashlib
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
    
    def _get_file_checksums(self, directory: Path) -> Dict[str, str]:
        """
        Get checksums of all Python files in a directory for change detection.
        
        Args:
            directory: Directory to scan
            
        Returns:
            Dictionary mapping file paths to their MD5 checksums
        """
        checksums = {}
        try:
            for file_path in directory.rglob("*.py"):
                if file_path.is_file():
                    try:
                        with open(file_path, 'rb') as f:
                            content = f.read()
                            checksums[str(file_path.relative_to(self.project_root))] = hashlib.md5(content).hexdigest()
                    except Exception as e:
                        logger.warning(f"⚠️ Could not read {file_path}: {e}")
            return checksums
        except Exception as e:
            logger.error(f"❌ Error scanning directory {directory}: {e}")
            return {}
    
    def _detect_file_changes(self, before_checksums: Dict[str, str], after_checksums: Dict[str, str]) -> List[str]:
        """
        Detect which files were changed.
        
        Args:
            before_checksums: Checksums before execution
            after_checksums: Checksums after execution
            
        Returns:
            List of changed file paths
        """
        changed_files = []
        
        # Check for modified files
        for file_path, checksum in after_checksums.items():
            if file_path in before_checksums:
                if before_checksums[file_path] != checksum:
                    changed_files.append(f"Modified: {file_path}")
            else:
                changed_files.append(f"Created: {file_path}")
        
        # Check for deleted files
        for file_path in before_checksums:
            if file_path not in after_checksums:
                changed_files.append(f"Deleted: {file_path}")
        
        return changed_files
    
    def _execute_claude_command(self) -> bool:
        """
        Execute Claude Code command to process all tasks.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🤖 Executing Claude Code command...")
            
            # Get file checksums before execution to detect changes
            logger.info("📊 Scanning files before Claude Code execution...")
            before_checksums = self._get_file_checksums(self.project_root / "src")
            logger.info(f"📁 Found {len(before_checksums)} Python files to monitor")
            
            # Change to project root directory for Claude Code execution
            original_cwd = os.getcwd()
            os.chdir(self.project_root)
            
            try:
                # Execute Claude Code with the predefined prompt
                # Using comprehensive prompt to ensure it modifies files
                prompt = """Process all tasks from the task master in sequence. For each task:
1. Read the task details carefully
2. Implement the required functionality by modifying source files
3. Write or update code files as needed
4. Ensure all changes are saved to disk
5. Complete the task fully before moving to the next one
6. Don't stop until ALL tasks are completed
7. After completing all tasks, close the app

IMPORTANT: You must modify actual source files in the project. Don't just plan - implement the code changes."""
                
                # Try different command formats for better compatibility
                cmd_variants = [
                    ["claude", "-p", prompt],  # Standard interactive mode first
                    ["claude", "--auto-approve", "-p", prompt],
                    ["claude", "--headless", "-p", prompt]
                ]
                
                success = False
                last_error = None
                
                for cmd in cmd_variants:
                    try:
                        logger.info(f"🚀 Trying command: {' '.join(cmd)}")
                        
                        # Set environment variables for better Claude Code behavior
                        env = os.environ.copy()
                        env.update({
                            'CLAUDE_AUTO_APPROVE': 'true' if '--auto-approve' in cmd else 'false',
                            'CLAUDE_HEADLESS': 'true' if '--headless' in cmd else 'false',
                            'CLAUDE_PROJECT_ROOT': str(self.project_root),
                            'PYTHONPATH': str(self.project_root / 'src'),
                            'CLAUDE_WORKING_DIR': str(self.project_root)
                        })
                        
                        # Ensure Claude settings directory exists with proper permissions
                        claude_dir = self.project_root / ".claude"
                        claude_dir.mkdir(exist_ok=True)
                        
                        # Create settings file if it doesn't exist
                        settings_file = claude_dir / "settings.json"
                        if not settings_file.exists():
                            settings_content = {
                                "allowedTools": [
                                    "Edit", "MultiEdit", "Write", "Read", "Bash", 
                                    "LS", "Glob", "Grep", "TodoWrite", "mcp__task_master_ai__*"
                                ],
                                "autoApprove": "--auto-approve" in cmd,
                                "headless": "--headless" in cmd,
                                "maxTokens": 200000,
                                "workingDirectory": str(self.project_root)
                            }
                            with open(settings_file, 'w') as f:
                                json.dump(settings_content, f, indent=2)
                            logger.info(f"📋 Created Claude settings at {settings_file}")
                        
                        # Execute with extended timeout and proper environment
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=3600,  # 1 hour timeout
                            cwd=self.project_root,
                            env=env
                        )
                        
                        logger.info(f"📊 Claude Code exit code: {result.returncode}")
                        
                        # Log stdout (more lines for better debugging)
                        if result.stdout:
                            logger.info("📋 Claude Code stdout:")
                            stdout_lines = result.stdout.split('\n')
                            for i, line in enumerate(stdout_lines[:20]):  # Log first 20 lines
                                if line.strip():
                                    logger.info(f"   {i+1:2d}: {line}")
                            if len(stdout_lines) > 20:
                                logger.info(f"   ... ({len(stdout_lines) - 20} more lines)")
                        
                        # Log stderr
                        if result.stderr:
                            logger.warning("⚠️ Claude Code stderr:")
                            stderr_lines = result.stderr.split('\n')
                            for i, line in enumerate(stderr_lines[:10]):  # Log first 10 lines
                                if line.strip():
                                    logger.warning(f"   {i+1:2d}: {line}")
                            if len(stderr_lines) > 10:
                                logger.warning(f"   ... ({len(stderr_lines) - 10} more lines)")
                        
                        # Consider exit code 0 as success
                        if result.returncode == 0:
                            success = True
                            logger.info("✅ Claude Code execution completed successfully")
                            break
                        else:
                            last_error = f"Exit code {result.returncode}"
                            logger.warning(f"⚠️ Command failed with exit code {result.returncode}, trying next variant...")
                            
                    except subprocess.TimeoutExpired:
                        last_error = "Timeout after 1 hour"
                        logger.warning("⚠️ Command timed out, trying next variant...")
                        continue
                    except FileNotFoundError:
                        last_error = "Claude command not found"
                        logger.warning("⚠️ Claude command not found, trying next variant...")
                        continue
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(f"⚠️ Command failed with error: {e}, trying next variant...")
                        continue
                
                if not success:
                    logger.error(f"❌ All Claude Code command variants failed. Last error: {last_error}")
                else:
                    # Check for file changes after successful execution
                    logger.info("📊 Scanning files after Claude Code execution...")
                    after_checksums = self._get_file_checksums(self.project_root / "src")
                    changed_files = self._detect_file_changes(before_checksums, after_checksums)
                    
                    if changed_files:
                        logger.info(f"✅ Claude Code made changes to {len(changed_files)} files:")
                        for change in changed_files[:10]:  # Show first 10 changes
                            logger.info(f"   📝 {change}")
                        if len(changed_files) > 10:
                            logger.info(f"   ... and {len(changed_files) - 10} more files")
                    else:
                        logger.warning("⚠️ No file changes detected - Claude Code may not have modified source files")
                        logger.info("💡 This could mean:")
                        logger.info("   - Tasks were already implemented")
                        logger.info("   - Claude Code encountered permission issues")
                        logger.info("   - Tasks only involved reading/analysis without code changes")
                
                return success
                
            finally:
                # Always restore original working directory
                os.chdir(original_cwd)
                
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