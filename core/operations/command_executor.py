import os
import subprocess
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import shlex
from utils.logging_config import get_logger

logger = get_logger(__name__)


class CommandExecutor:
    def __init__(self, base_dir: str = None, timeout: int = 120):
        """
        Initialize CommandExecutor
        
        Args:
            base_dir: Base directory for command execution (defaults to current directory)
            timeout: Default timeout for commands in seconds (default: 5 minutes)
        """
        self.base_dir = base_dir or os.getcwd()
        self.timeout = timeout
        logger.info(f"🔧 CommandExecutor initialized with base_dir: {self.base_dir}")
    
    def execute_taskmaster_command(self, ticket_ids: List[str], refined_dir: str = None) -> Dict[str, Any]:
        """
        Execute task-master parse-prd command for each validated ticket file.
        
        Args:
            ticket_ids: List of validated ticket IDs that have corresponding files
            refined_dir: Directory containing the refined markdown files (defaults to {base_dir}/src/tasks/refined)
        
        Returns:
            Dictionary with execution results for each ticket
        """
        # Use consistent path calculation with main.py approach
        if refined_dir is None:
            # Default to src/tasks/refined relative to the base_dir (project root)
            tasks_base_dir = os.path.join(self.base_dir, "src", "tasks")
            refined_dir = os.path.join(tasks_base_dir, "refined")
            # Normalize the path to remove any ./ components
            refined_dir = os.path.normpath(refined_dir)
        
        logger.info(f"🚀 Starting task-master command execution for {len(ticket_ids)} tickets")
        logger.info(f"📁 Base directory: {self.base_dir}")
        logger.info(f"📁 Tasks base directory: {tasks_base_dir}")
        logger.info(f"📁 Looking for files in: {refined_dir}")
        
        results = {
            "successful_executions": [],
            "failed_executions": [],
            "total_processed": len(ticket_ids),
            "success_count": 0,
            "failure_count": 0
        }
        
        for i, ticket_id in enumerate(ticket_ids):
            try:
                logger.info(f"📄 Processing ticket {i+1}/{len(ticket_ids)}: {ticket_id}")
                
                # Construct the file path
                file_patterns = [
                    f"NOMAD-{ticket_id}.md",
                    f"{ticket_id}.md",
                    f"TICKET-{ticket_id}.md"
                ]
                
                file_path = None
                for pattern in file_patterns:
                    potential_path = os.path.join(refined_dir, pattern)
                    if os.path.exists(potential_path):
                        file_path = potential_path
                        break
                
                if not file_path:
                    raise FileNotFoundError(f"No file found for ticket {ticket_id} in {refined_dir}")
                
                logger.info(f"📁 Using file: {file_path}")
                
                # Execute the task-master command
                execution_result = self._run_taskmaster_parse_prd(file_path, ticket_id)
                
                results["successful_executions"].append({
                    "ticket_id": ticket_id,
                    "file_path": file_path,
                    "command": execution_result["command"],
                    "exit_code": execution_result["exit_code"],
                    "execution_time": execution_result["execution_time"],
                    "output_preview": execution_result["stdout"][:200] + "..." if len(execution_result["stdout"]) > 200 else execution_result["stdout"]
                })
                results["success_count"] += 1
                
                logger.info(f"✅ Successfully executed task-master for ticket {ticket_id}")
                
            except Exception as e:
                error_info = {
                    "ticket_id": ticket_id,
                    "error": str(e),
                    "file_path": file_path if 'file_path' in locals() else "unknown"
                }
                results["failed_executions"].append(error_info)
                results["failure_count"] += 1
                
                logger.error(f"❌ Failed to execute task-master for ticket {ticket_id}: {e}")
                continue
        
        # Summary logging
        logger.info(f"📊 Task-master execution completed:")
        logger.info(f"   ✅ Successful executions: {results['success_count']}")
        logger.info(f"   ❌ Failed executions: {results['failure_count']}")
        
        if results['total_processed'] > 0:
            success_rate = (results['success_count']/results['total_processed']*100)
            logger.info(f"   📊 Success rate: {success_rate:.1f}%")
        else:
            logger.info(f"   📊 Success rate: N/A (no tickets processed)")
        
        if results["failed_executions"]:
            failed_ids = [f["ticket_id"] for f in results["failed_executions"]]
            logger.warning(f"⚠️ Failed ticket IDs: {failed_ids}")
        
        return results
    
    def _run_taskmaster_parse_prd(self, file_path: str, ticket_id: str) -> Dict[str, Any]:
        """
        Run the task-master parse-prd command for a specific file.
        
        Args:
            file_path: Path to the markdown file
            ticket_id: Ticket ID for logging purposes
        
        Returns:
            Dictionary with command execution results
        """
        import time
        start_time = time.time()
        
        # Construct the command with --force flag for automation
        command = ["task-master", "parse-prd", file_path, "--force"]  
        command_str = " ".join(shlex.quote(arg) for arg in command)
        
        logger.info(f"🔧 Executing command: {command_str}")
        logger.info(f"📁 Working directory: {self.base_dir}")
        logger.info(f"⏰ Timeout set to: {self.timeout} seconds")
        
        try:
            # Execute the command
            result = subprocess.run(
                command,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False  # Don't raise exception on non-zero exit code
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
                raise subprocess.CalledProcessError(
                    result.returncode, 
                    command_str, 
                    output=result.stdout, 
                    stderr=result.stderr
                )
            
            return {
                "command": command_str,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": execution_time
            }
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            error_msg = f"Command timed out after {self.timeout} seconds"
            logger.error(f"⏰ {error_msg}")
            raise TimeoutError(error_msg)
            
        except subprocess.CalledProcessError as e:
            execution_time = time.time() - start_time
            error_msg = f"Command failed with exit code {e.returncode}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"📤 Error output: {e.stderr}")
            raise RuntimeError(f"{error_msg}: {e.stderr}")
            
        except FileNotFoundError:
            error_msg = "task-master command not found. Make sure it's installed and in PATH"
            logger.error(f"❌ {error_msg}")
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
                ["task-master", "--version"],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=10,
                check=False
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
            logger.error("❌ task-master command not found in PATH")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error testing task-master availability: {e}")
            return False