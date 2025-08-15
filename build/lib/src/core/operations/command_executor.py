import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.managers.feedback_manager import FeedbackManager, ProcessingStage
from src.utils.file_operations import get_tasks_dir
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CommandExecutor:
    def __init__(self, base_dir: str = None, timeout: int = 120, feedback_manager: FeedbackManager = None):
        """
        Initialize CommandExecutor

        Args:
            base_dir: Base directory for command execution (defaults to current directory)
            timeout: Default timeout for commands in seconds (default: 5 minutes)
            feedback_manager: Optional FeedbackManager for providing user feedback
        """
        # For global installation mode, use the actual working directory where the user is
        # For development mode, use the provided base_dir or current directory
        if base_dir is None:
            self.base_dir = os.getcwd()
        else:
            # Ensure we're using the actual working directory for global mode
            # Check if base_dir is pointing to the nomad project directory
            nomad_indicators = ["entry", "core", "clients", "utils"]
            if all(os.path.exists(os.path.join(base_dir, indicator)) for indicator in nomad_indicators):
                # This appears to be the nomad project directory, use cwd instead
                logger.warning(f"⚠️ Base directory appears to be nomad project directory: {base_dir}")
                logger.warning(f"⚠️ Using current working directory instead: {os.getcwd()}")
                self.base_dir = os.getcwd()
            else:
                self.base_dir = base_dir

        self.timeout = timeout
        self.feedback_manager = feedback_manager

        # Set up taskmaster path - use TASKMASTER_DIR env var or default to ./taskmaster
        self.taskmaster_path = self._get_taskmaster_path()
        logger.info(f"🔧 CommandExecutor initialized with base_dir: {self.base_dir}")
        logger.info(f"🔧 Using taskmaster path: {self.taskmaster_path}")
        if self.feedback_manager:
            logger.info(f"🔧 FeedbackManager integration enabled")

    def _get_taskmaster_path(self) -> str:
        """
        Get the path to the taskmaster executable.
        First checks for globally installed task-master, then uses TASKMASTER_DIR environment variable or defaults to ./taskmaster

        Returns:
            Path to taskmaster executable
        """
        # First try to use globally installed task-master
        try:
            import shutil

            global_taskmaster = shutil.which("task-master")
            if global_taskmaster:
                logger.info(f"✅ Found globally installed task-master at: {global_taskmaster}")
                return global_taskmaster
        except Exception as e:
            logger.warning(f"⚠️ Error checking for global task-master: {e}")

        # Fall back to local installation
        taskmaster_dir = os.environ.get("TASKMASTER_DIR", "./taskmaster")

        # If it's a relative path, make it relative to base_dir
        if not os.path.isabs(taskmaster_dir):
            taskmaster_dir = os.path.join(self.base_dir, taskmaster_dir)

        # The actual executable path
        taskmaster_path = os.path.join(taskmaster_dir, "task-master")

        # On Windows, add .exe extension if not present
        if os.name == "nt" and not taskmaster_path.endswith(".exe"):
            taskmaster_path += ".exe"

        logger.warning(f"⚠️ Using local taskmaster path (global not found): {taskmaster_path}")
        return taskmaster_path

    def execute_taskmaster_command(self, ticket_ids: List[str], refined_dir: str = None, page_id: str = None) -> Dict[str, Any]:
        """
        Execute task-master parse-prd command for each validated ticket file.

        Args:
            ticket_ids: List of validated ticket IDs that have corresponding files
            refined_dir: Directory containing the refined markdown files (defaults to {base_dir}/tasks/refined)
            page_id: Optional Notion page ID for feedback updates

        Returns:
            Dictionary with execution results for each ticket
        """
        # Use consistent path calculation with main.py approach
        if refined_dir is None:
            # Use TASKS_DIR environment variable or default to './tasks'
            tasks_base_dir = get_tasks_dir()
            refined_dir = os.path.join(tasks_base_dir, "refined")
            # Normalize the path to remove any ./ components
            refined_dir = os.path.normpath(refined_dir)

        logger.info(f"🚀 Starting task-master command execution for {len(ticket_ids)} tickets")
        logger.info(f"📁 Base directory: {self.base_dir}")
        logger.info(f"📁 Tasks base directory: {tasks_base_dir}")
        logger.info(f"📁 Looking for files in: {refined_dir}")

        # Add feedback if manager is available
        if self.feedback_manager and page_id:
            self.feedback_manager.add_feedback(
                page_id,
                ProcessingStage.PREPARING,
                f"Starting task-master execution for {len(ticket_ids)} ticket(s)",
                details=f"Base directory: {self.base_dir}\nRefined files directory: {refined_dir}",
            )

        # Safety check: Warn if multiple tickets provided (should only be 1 to avoid conflicts)
        if len(ticket_ids) > 1:
            logger.warning(f"⚠️ Multiple tickets provided ({len(ticket_ids)}). This may cause tasks.json conflicts!")
            logger.warning("⚠️ Consider processing one ticket at a time to avoid overwrites.")

            if self.feedback_manager and page_id:
                self.feedback_manager.add_feedback(
                    page_id,
                    ProcessingStage.PREPARING,
                    f"Processing multiple tickets simultaneously ({len(ticket_ids)})",
                    details="Warning: This may cause tasks.json conflicts. Consider processing one ticket at a time.",
                )

        results = {
            "successful_executions": [],
            "failed_executions": [],
            "total_processed": len(ticket_ids),
            "success_count": 0,
            "failure_count": 0,
        }

        for i, ticket_id in enumerate(ticket_ids):
            try:
                logger.info(f"📄 Processing ticket {i+1}/{len(ticket_ids)}: {ticket_id}")

                # Add feedback for individual ticket processing
                if self.feedback_manager and page_id:
                    self.feedback_manager.add_feedback(
                        page_id,
                        ProcessingStage.PROCESSING,
                        f"Processing ticket {i+1}/{len(ticket_ids)}: {ticket_id}",
                        details="Searching for ticket file and executing task-master command",
                    )

                # Construct the file path
                file_patterns = [
                    f"NOMAD-{ticket_id}.md",
                    f"{ticket_id}.md",
                    f"TICKET-{ticket_id}.md",
                ]

                file_path = None
                for pattern in file_patterns:
                    potential_path = os.path.join(refined_dir, pattern)
                    if os.path.exists(potential_path):
                        file_path = potential_path
                        break

                if not file_path:
                    error_msg = f"No file found for ticket {ticket_id} in {refined_dir}"
                    if self.feedback_manager and page_id:
                        self.feedback_manager.add_error_feedback(
                            page_id,
                            ProcessingStage.PROCESSING,
                            "Ticket file not found",
                            details=f"Searched for patterns: {file_patterns}\nIn directory: {refined_dir}",
                        )
                    raise FileNotFoundError(error_msg)

                logger.info(f"📁 Using file: {file_path}")

                if self.feedback_manager and page_id:
                    self.feedback_manager.add_feedback(
                        page_id,
                        ProcessingStage.PROCESSING,
                        f"Found ticket file: {os.path.basename(file_path)}",
                        details=f"Executing task-master parse-prd command",
                    )

                # Execute the task-master command
                execution_result = self._run_taskmaster_parse_prd(file_path, ticket_id, page_id)

                results["successful_executions"].append(
                    {
                        "ticket_id": ticket_id,
                        "file_path": file_path,
                        "command": execution_result["command"],
                        "exit_code": execution_result["exit_code"],
                        "execution_time": execution_result["execution_time"],
                        "output_preview": (execution_result["stdout"][:200] + "..." if len(execution_result["stdout"]) > 200 else execution_result["stdout"]),
                    }
                )
                results["success_count"] += 1

                logger.info(f"✅ Successfully executed task-master for ticket {ticket_id}")

                if self.feedback_manager and page_id:
                    self.feedback_manager.add_feedback(
                        page_id,
                        ProcessingStage.PROCESSING,
                        f"Successfully processed ticket {ticket_id}",
                        details=f"Task-master execution completed for {os.path.basename(file_path)}",
                    )

            except Exception as e:
                error_info = {
                    "ticket_id": ticket_id,
                    "error": str(e),
                    "file_path": file_path if "file_path" in locals() else "unknown",
                }
                results["failed_executions"].append(error_info)
                results["failure_count"] += 1

                logger.error(f"❌ Failed to execute task-master for ticket {ticket_id}: {e}")

                if self.feedback_manager and page_id:
                    self.feedback_manager.add_error_feedback(
                        page_id,
                        ProcessingStage.PROCESSING,
                        f"Failed to process ticket {ticket_id}",
                        details=f"Error: {str(e)}\nFile path: {file_path if 'file_path' in locals() else 'unknown'}",
                    )

                continue

        # Summary logging
        logger.info(f"📊 Task-master execution completed:")
        logger.info(f"   ✅ Successful executions: {results['success_count']}")
        logger.info(f"   ❌ Failed executions: {results['failure_count']}")

        if results["total_processed"] > 0:
            success_rate = results["success_count"] / results["total_processed"] * 100
            logger.info(f"   📊 Success rate: {success_rate:.1f}%")
        else:
            logger.info(f"   📊 Success rate: N/A (no tickets processed)")

        if results["failed_executions"]:
            failed_ids = [f["ticket_id"] for f in results["failed_executions"]]
            logger.warning(f"⚠️ Failed ticket IDs: {failed_ids}")

        return results

    def _run_taskmaster_parse_prd(self, file_path: str, ticket_id: str, page_id: str = None) -> Dict[str, Any]:
        """
        Run the task-master parse-prd command for a specific file.

        Args:
            file_path: Path to the markdown file
            ticket_id: Ticket ID for logging purposes
            page_id: Optional Notion page ID for feedback updates

        Returns:
            Dictionary with command execution results
        """
        import time

        start_time = time.time()

        # Construct the command with --force flag for automation
        command = [self.taskmaster_path, "parse-prd", file_path, "--force"]
        command_str = " ".join(shlex.quote(arg) for arg in command)

        logger.info(f"🔧 Executing command: {command_str}")
        logger.info(f"📁 Working directory: {self.base_dir}")
        logger.info(f"⏰ Timeout set to: {self.timeout} seconds")

        if self.feedback_manager and page_id:
            self.feedback_manager.add_feedback(
                page_id,
                ProcessingStage.PROCESSING,
                f"Executing task-master parse-prd command",
                details=f"Command: {command_str}\nWorking directory: {self.base_dir}\nTimeout: {self.timeout}s",
            )

        try:
            # Execute the command
            result = subprocess.run(
                command,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,  # Don't raise exception on non-zero exit code
            )

            execution_time = time.time() - start_time

            # Log command output
            if result.stdout:
                logger.info(f"📤 Command stdout:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"📤 Command stderr:\n{result.stderr}")

            logger.info(f"⏱️  Command completed in {execution_time:.2f} seconds with exit code {result.returncode}")

            # Check if command was successful
            if result.returncode != 0:
                error_msg = f"Command failed with exit code {result.returncode}"
                if self.feedback_manager and page_id:
                    self.feedback_manager.add_error_feedback(
                        page_id,
                        ProcessingStage.PROCESSING,
                        error_msg,
                        details=f"stdout: {result.stdout}\nstderr: {result.stderr}",
                    )
                raise subprocess.CalledProcessError(result.returncode, command_str, output=result.stdout, stderr=result.stderr)

            # Additional validation: Check if tasks.json was actually generated with valid content
            if not self._validate_taskmaster_output():
                error_msg = "task-master parse-prd completed but failed to generate valid tasks.json file"
                if self.feedback_manager and page_id:
                    self.feedback_manager.add_error_feedback(
                        page_id,
                        ProcessingStage.PROCESSING,
                        "Task validation failed",
                        details=error_msg,
                    )
                raise RuntimeError(error_msg)

            return {
                "command": command_str,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": execution_time,
            }

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            error_msg = f"Command timed out after {self.timeout} seconds"
            logger.error(f"⏰ {error_msg}")
            if self.feedback_manager and page_id:
                self.feedback_manager.add_error_feedback(
                    page_id,
                    ProcessingStage.PROCESSING,
                    "Command execution timeout",
                    details=f"Timeout: {self.timeout}s\nExecution time: {execution_time:.2f}s",
                )
            raise TimeoutError(error_msg)

        except subprocess.CalledProcessError as e:
            execution_time = time.time() - start_time
            error_msg = f"Command failed with exit code {e.returncode}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"📤 Error output: {e.stderr}")
            if self.feedback_manager and page_id:
                self.feedback_manager.add_error_feedback(
                    page_id,
                    ProcessingStage.PROCESSING,
                    error_msg,
                    details=f"stderr: {e.stderr}\nExecution time: {execution_time:.2f}s",
                )
            raise RuntimeError(f"{error_msg}: {e.stderr}")

        except FileNotFoundError:
            error_msg = f"task-master command not found at {self.taskmaster_path}. Make sure TASKMASTER_DIR is set correctly or ./taskmaster directory exists"
            logger.error(f"❌ {error_msg}")
            if self.feedback_manager and page_id:
                self.feedback_manager.add_error_feedback(
                    page_id,
                    ProcessingStage.PROCESSING,
                    "Task-master command not found",
                    details=f"Path: {self.taskmaster_path}\nCheck TASKMASTER_DIR environment variable",
                )
            raise FileNotFoundError(error_msg)

    def test_taskmaster_availability(self) -> bool:
        """
        Test if task-master command is available and working.

        Returns:
            True if task-master is available, False otherwise
        """
        try:
            logger.info("🧪 Testing task-master availability...")

            result = subprocess.run(
                [self.taskmaster_path, "--version"],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode == 0:
                logger.info(f"✅ task-master is available: {result.stdout.strip()}")
                return True
            else:
                logger.warning(f"⚠️ task-master returned non-zero exit code: {result.returncode}")
                logger.warning(f"📤 Error: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("⏰ task-master --version command timed out")
            return False

        except FileNotFoundError:
            logger.error(f"❌ task-master command not found at {self.taskmaster_path}")
            return False

        except Exception as e:
            logger.error(f"❌ Error testing task-master availability: {e}")
            return False

    def _validate_taskmaster_output(self) -> bool:
        """
        Validate that task-master parse-prd generated a valid tasks.json file.

        Returns:
            True if tasks.json exists and contains valid task data, False otherwise
        """
        try:
            import json

            # Check if tasks.json file exists in .taskmaster/tasks/
            tasks_file_path = os.path.join(self.base_dir, ".taskmaster", "tasks", "tasks.json")

            if not os.path.exists(tasks_file_path):
                logger.error(f"❌ tasks.json file not found at {tasks_file_path}")
                return False

            # Check if file has content and is valid JSON
            with open(tasks_file_path, "r", encoding="utf-8") as f:
                try:
                    tasks_data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ tasks.json contains invalid JSON: {e}")
                    return False

            # Basic validation: should be a dict with some expected structure
            if not isinstance(tasks_data, dict):
                logger.error("❌ tasks.json should contain a JSON object")
                return False

            # Check if it has the correct taskmaster structure
            # The actual structure has tag names as keys (like "master") containing tasks and metadata
            has_valid_structure = False
            for key, value in tasks_data.items():
                if isinstance(value, dict) and ("tasks" in value or "metadata" in value):
                    has_valid_structure = True
                    break

            if not has_valid_structure:
                logger.error("❌ tasks.json missing expected taskmaster structure (should have tag objects with tasks/metadata)")
                return False

            # Check file size is reasonable (not empty or too small)
            file_stat = os.stat(tasks_file_path)
            if file_stat.st_size < 50:  # Very minimal JSON would be larger than 50 bytes
                logger.error(f"❌ tasks.json file too small ({file_stat.st_size} bytes), likely incomplete")
                return False

            logger.info(f"✅ tasks.json validation passed: {file_stat.st_size} bytes, valid structure")
            return True

        except Exception as e:
            logger.error(f"❌ Error validating tasks.json: {e}")
            return False
