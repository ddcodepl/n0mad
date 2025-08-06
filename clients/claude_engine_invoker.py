import subprocess
import threading
import time
import os
import signal
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from utils.logging_config import get_logger

logger = get_logger(__name__)


class InvocationResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ClaudeInvocation:
    """Represents a Claude engine invocation"""
    invocation_id: str
    ticket_id: str
    page_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[InvocationResult] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None
    process_id: Optional[int] = None
    duration_seconds: Optional[float] = None


class ClaudeEngineInvoker:
    """
    Secure mechanism to invoke Claude Code CLI with predefined prompts.
    Includes audit logging, timeout mechanisms, and retry logic.
    """
    
    def __init__(self, project_root: str, timeout_minutes: int = 30, max_retries: int = 2):
        self.project_root = project_root
        self.timeout_seconds = timeout_minutes * 60
        self.max_retries = max_retries
        self._invocation_lock = threading.RLock()
        self._invocation_history: List[ClaudeInvocation] = []
        self._max_history = 100
        self._active_processes: Dict[str, subprocess.Popen] = {}
        
        # Base prompt template - will be customized per task
        self.base_prompt_template = """Execute TaskMaster task for ticket: {ticket_id}

Task Context:
- Ticket ID: {ticket_id}
- Notion Page ID: {page_id}

CRITICAL INSTRUCTIONS - ACTUAL CODE IMPLEMENTATION REQUIRED:
1. Use `task-master next` to find the next available task
2. Use `task-master show <id>` to get detailed task information
3. **MANDATORY: IMPLEMENT ACTUAL CODE** - Create/modify files, write functions, add classes, implement features
4. **VERIFICATION REQUIRED**: Before marking any task complete, run `git status` to verify files were modified
5. **IMPLEMENTATION REQUIREMENTS**:
   - Create new .py files when required
   - Modify existing files to add/update functionality  
   - Write actual function implementations, not just stubs
   - Add proper error handling and logging
   - Include imports and dependencies
6. **TESTING REQUIRED**: Test implementations to ensure they work correctly
7. **ONLY mark as done AFTER**:
   - Writing actual code that implements the task requirements
   - Verifying with `git status` that files were changed
   - Testing the implementation works
8. Use `task-master set-status --id=<id> --status=done` ONLY after completing real implementation
9. Continue processing until ALL pending tasks have working code implementations

ABSOLUTE REQUIREMENT: Every completed task MUST result in actual file modifications visible in `git status`. 
Tasks without file changes will be considered FAILED and rolled back to pending status.

If a task seems unclear, use `task-master show <id>` for details before implementing."""

        # Task Master specific prompt template
        self.taskmaster_prompt_template = """Execute Task Master AI task: {task_id}

Task Context:
- Task Master Task ID: {task_id}  
- Page ID: {page_id}

TASK MASTER INTEGRATION - DIRECT MCP TOOL USAGE:
1. **REQUIRED: Use Task Master MCP tools directly** - You have access to Task Master MCP tools
2. Start by getting task details: Use the MCP tool `mcp__task-master-ai__get_task` with id="{task_id}" and projectRoot="/Users/damian/Web/ddcode/nomad"
3. Set task status to in-progress: Use `mcp__task-master-ai__set_task_status` with id="{task_id}", status="in-progress", projectRoot="/Users/damian/Web/ddcode/nomad"
4. **MANDATORY: IMPLEMENT ACTUAL CODE** - Create/modify files, write functions, add classes, implement features based on task requirements
5. **VERIFICATION REQUIRED**: Before marking any task complete, run `git status` to verify files were modified
6. **IMPLEMENTATION REQUIREMENTS**:
   - Create new .py files when required
   - Modify existing files to add/update functionality
   - Write actual function implementations, not just stubs  
   - Add proper error handling and logging
   - Include imports and dependencies
7. **TESTING REQUIRED**: Test implementations to ensure they work correctly
8. Update task progress: Use `mcp__task-master-ai__update_subtask` or `mcp__task-master-ai__update_task` to log implementation details
9. **ONLY mark as done AFTER**:
   - Writing actual code that implements the task requirements
   - Verifying with `git status` that files were changed
   - Testing the implementation works
10. Complete task: Use `mcp__task-master-ai__set_task_status` with id="{task_id}", status="done", projectRoot="/Users/damian/Web/ddcode/nomad"

ABSOLUTE REQUIREMENT: Every completed task MUST result in actual file modifications visible in `git status`.
Tasks without file changes will be considered FAILED and rolled back to pending status.

PROJECT ROOT: /Users/damian/Web/ddcode/nomad
USE MCP TOOLS: You have direct access to Task Master MCP tools - use them instead of CLI commands."""
        
        logger.info(f"🤖 ClaudeEngineInvoker initialized with timeout: {timeout_minutes}m, retries: {max_retries}")
        logger.info(f"📁 Project root: {project_root}")
        
    def invoke_claude_engine(self, ticket_id: str, page_id: str) -> ClaudeInvocation:
        """
        Invoke Claude Code CLI with the predefined prompt for task processing.
        
        Args:
            ticket_id: Ticket ID for audit logging
            page_id: Notion page ID for context
            
        Returns:
            ClaudeInvocation object with execution results
        """
        invocation_id = f"{ticket_id}_{int(time.time())}"
        
        invocation = ClaudeInvocation(
            invocation_id=invocation_id,
            ticket_id=ticket_id,
            page_id=page_id,
            start_time=datetime.now()
        )
        
        # Generate customized prompt for this specific task
        customized_prompt = self.base_prompt_template.format(
            ticket_id=ticket_id,
            page_id=page_id
        )
        
        # Audit logging - log invocation attempt
        logger.info(f"🚀 Starting Claude engine invocation")
        logger.info(f"   🎫 Ticket ID: {ticket_id}")
        logger.info(f"   📄 Page ID: {page_id[:8]}...")
        logger.info(f"   🆔 Invocation ID: {invocation_id}")
        logger.info(f"   ⏰ Timeout: {self.timeout_seconds}s")
        logger.info(f"   📝 Prompt: {customized_prompt[:100]}...")
        
        with self._invocation_lock:
            try:
                # Attempt invocation with retries
                for attempt in range(self.max_retries + 1):
                    if attempt > 0:
                        logger.info(f"🔄 Retry attempt {attempt}/{self.max_retries}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    
                    try:
                        result = self._execute_claude_command(invocation, customized_prompt)
                        
                        if result.result == InvocationResult.SUCCESS:
                            logger.info(f"✅ Claude engine invocation successful on attempt {attempt + 1}")
                            break
                        elif result.result == InvocationResult.TIMEOUT:
                            logger.warning(f"⏰ Claude engine invocation timed out on attempt {attempt + 1}")
                            if attempt < self.max_retries:
                                continue
                        else:
                            logger.error(f"❌ Claude engine invocation failed on attempt {attempt + 1}: {result.error}")
                            if attempt < self.max_retries:
                                continue
                    
                    except Exception as e:
                        logger.error(f"❌ Exception during Claude invocation attempt {attempt + 1}: {e}")
                        invocation.error = str(e)
                        invocation.result = InvocationResult.FAILED
                        if attempt < self.max_retries:
                            continue
                
                # Finalize invocation
                invocation.end_time = datetime.now()
                if invocation.start_time and invocation.end_time:
                    invocation.duration_seconds = (invocation.end_time - invocation.start_time).total_seconds()
                
                # Add to history
                self._add_to_history(invocation)
                
                # Final audit logging
                logger.info(f"🏁 Claude engine invocation completed")
                logger.info(f"   🎫 Ticket ID: {ticket_id}")
                logger.info(f"   📊 Result: {invocation.result}")
                logger.info(f"   ⏱️ Duration: {invocation.duration_seconds:.2f}s")
                if invocation.exit_code is not None:
                    logger.info(f"   🚪 Exit code: {invocation.exit_code}")
                
                return invocation
                
            except Exception as e:
                logger.error(f"❌ Critical error in Claude engine invocation: {e}")
                invocation.error = str(e)
                invocation.result = InvocationResult.FAILED
                invocation.end_time = datetime.now()
                if invocation.start_time and invocation.end_time:
                    invocation.duration_seconds = (invocation.end_time - invocation.start_time).total_seconds()
                self._add_to_history(invocation)
                return invocation
    
    def invoke_claude_engine_with_taskmaster(self, task_id: str, page_id: str) -> ClaudeInvocation:
        """
        Invoke Claude Code CLI with Task Master specific prompt and MCP tool integration.
        
        Args:
            task_id: Task Master task ID
            page_id: Page ID for context (usually same as task_id for Task Master)
            
        Returns:
            ClaudeInvocation object with execution results
        """
        invocation_id = f"tm_{task_id}_{int(time.time())}"
        
        invocation = ClaudeInvocation(
            invocation_id=invocation_id,
            ticket_id=task_id,
            page_id=page_id,
            start_time=datetime.now()
        )
        
        # Generate Task Master specific prompt
        customized_prompt = self.taskmaster_prompt_template.format(
            task_id=task_id,
            page_id=page_id
        )
        
        # Audit logging - log invocation attempt
        logger.info(f"🚀 Starting Task Master Claude engine invocation")
        logger.info(f"   🎯 Task Master Task ID: {task_id}")
        logger.info(f"   📄 Page ID: {page_id}")
        logger.info(f"   🆔 Invocation ID: {invocation_id}")
        logger.info(f"   ⏰ Timeout: {self.timeout_seconds}s")
        logger.info(f"   📝 Using Task Master MCP prompt template")
        
        with self._invocation_lock:
            try:
                # Attempt invocation with retries
                for attempt in range(self.max_retries + 1):
                    if attempt > 0:
                        logger.info(f"🔄 Task Master retry attempt {attempt}/{self.max_retries}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    
                    try:
                        result = self._execute_claude_command(invocation, customized_prompt)
                        
                        if result.result == InvocationResult.SUCCESS:
                            logger.info(f"✅ Task Master Claude engine invocation successful on attempt {attempt + 1}")
                            break
                        elif result.result == InvocationResult.TIMEOUT:
                            logger.warning(f"⏰ Task Master Claude engine invocation timed out on attempt {attempt + 1}")
                            if attempt < self.max_retries:
                                continue
                        else:
                            logger.error(f"❌ Task Master Claude engine invocation failed on attempt {attempt + 1}: {result.error}")
                            if attempt < self.max_retries:
                                continue
                    
                    except Exception as e:
                        logger.error(f"❌ Exception during Task Master Claude invocation attempt {attempt + 1}: {e}")
                        invocation.error = str(e)
                        invocation.result = InvocationResult.FAILED
                        if attempt < self.max_retries:
                            continue
                
                # Finalize invocation
                invocation.end_time = datetime.now()
                if invocation.start_time and invocation.end_time:
                    invocation.duration_seconds = (invocation.end_time - invocation.start_time).total_seconds()
                
                # Add to history
                self._add_to_history(invocation)
                
                # Final audit logging
                logger.info(f"🏁 Task Master Claude engine invocation completed")
                logger.info(f"   🎯 Task Master Task ID: {task_id}")
                logger.info(f"   📊 Result: {invocation.result}")
                logger.info(f"   ⏱️ Duration: {invocation.duration_seconds:.2f}s")
                if invocation.exit_code is not None:
                    logger.info(f"   🚪 Exit code: {invocation.exit_code}")
                
                return invocation
                
            except Exception as e:
                logger.error(f"❌ Critical error in Task Master Claude engine invocation: {e}")
                invocation.error = str(e)
                invocation.result = InvocationResult.FAILED
                invocation.end_time = datetime.now()
                if invocation.start_time and invocation.end_time:
                    invocation.duration_seconds = (invocation.end_time - invocation.start_time).total_seconds()
                self._add_to_history(invocation)
                return invocation
    
    def _execute_claude_command(self, invocation: ClaudeInvocation, prompt: str) -> ClaudeInvocation:
        """
        Execute the Claude Code CLI command with the specified prompt.
        
        Args:
            invocation: ClaudeInvocation object to update
            prompt: Customized prompt for this specific task
            
        Returns:
            Updated ClaudeInvocation object
        """
        try:
            # Construct Claude Code CLI command
            # Using the -p flag to pass the customized prompt directly
            cmd = [
                "claude",
                "-p", prompt
            ]
            
            logger.info(f"🔧 Executing command: {' '.join(cmd)}")
            logger.info(f"📁 Working directory: {self.project_root}")
            
            # Start the process
            process = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if os.name != 'nt' else None  # Create process group on Unix
            )
            
            invocation.process_id = process.pid
            self._active_processes[invocation.invocation_id] = process
            
            logger.info(f"🚀 Claude process started with PID: {process.pid}")
            
            try:
                # Wait for completion with timeout
                stdout, stderr = process.communicate(timeout=self.timeout_seconds)
                
                invocation.exit_code = process.returncode
                invocation.stdout = stdout
                invocation.stderr = stderr
                
                # Remove from active processes
                self._active_processes.pop(invocation.invocation_id, None)
                
                # Enhanced Claude output display
                if stdout:
                    logger.info(f"🤖 Claude Output ({len(stdout)} chars):")
                    for line in stdout.splitlines():
                        if line.strip():  # Skip empty lines
                            logger.info(f"    {line}")
                            print(f"🤖 Claude: {line}")  # Also print to console
                
                if process.returncode == 0:
                    invocation.result = InvocationResult.SUCCESS
                    logger.info(f"✅ Claude process completed successfully")
                    if stderr:
                        logger.warning(f"⚠️ Claude Stderr:")
                        for line in stderr.splitlines():
                            if line.strip():
                                logger.warning(f"    {line}")
                                print(f"⚠️ Claude Warning: {line}")
                else:
                    invocation.result = InvocationResult.FAILED
                    invocation.error = f"Process exited with code {process.returncode}"
                    logger.error(f"❌ Claude process failed with exit code: {process.returncode}")
                    if stderr:
                        logger.error(f"🚨 Claude Errors:")
                        for line in stderr.splitlines():
                            if line.strip():
                                logger.error(f"    {line}")
                                print(f"🚨 Claude Error: {line}")
                
            except subprocess.TimeoutExpired:
                logger.warning(f"⏰ Claude process timed out after {self.timeout_seconds}s")
                
                # Terminate the process group
                try:
                    if os.name != 'nt':
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    else:
                        process.terminate()
                    
                    # Give it a moment to terminate gracefully
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                        invocation.stdout = stdout
                        invocation.stderr = stderr
                    except subprocess.TimeoutExpired:
                        # Force kill if it doesn't terminate
                        if os.name != 'nt':
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        else:
                            process.kill()
                        stdout, stderr = process.communicate()
                        invocation.stdout = stdout
                        invocation.stderr = stderr
                
                except Exception as kill_error:
                    logger.error(f"❌ Error terminating Claude process: {kill_error}")
                
                invocation.result = InvocationResult.TIMEOUT
                invocation.error = f"Process timed out after {self.timeout_seconds}s"
                invocation.exit_code = process.returncode
                
                # Remove from active processes
                self._active_processes.pop(invocation.invocation_id, None)
                
        except FileNotFoundError:
            error_msg = "Claude Code CLI not found. Make sure 'claude' is installed and in PATH"
            logger.error(f"❌ {error_msg}")
            invocation.result = InvocationResult.FAILED
            invocation.error = error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error executing Claude command: {e}"
            logger.error(f"❌ {error_msg}")
            invocation.result = InvocationResult.FAILED
            invocation.error = error_msg
        
        return invocation
    
    def cancel_invocation(self, invocation_id: str) -> bool:
        """
        Cancel an active Claude invocation.
        
        Args:
            invocation_id: ID of the invocation to cancel
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        with self._invocation_lock:
            if invocation_id not in self._active_processes:
                logger.warning(f"⚠️ No active process found for invocation ID: {invocation_id}")
                return False
            
            process = self._active_processes[invocation_id]
            
            try:
                logger.info(f"⏹️ Cancelling Claude invocation: {invocation_id}")
                
                # Terminate process group
                if os.name != 'nt':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                
                # Give it time to terminate gracefully
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill
                    if os.name != 'nt':
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait()
                
                self._active_processes.pop(invocation_id, None)
                logger.info(f"✅ Successfully cancelled invocation: {invocation_id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error cancelling invocation {invocation_id}: {e}")
                return False
    
    def get_active_invocations(self) -> List[str]:
        """
        Get list of active invocation IDs.
        
        Returns:
            List of active invocation IDs
        """
        with self._invocation_lock:
            return list(self._active_processes.keys())
    
    def _add_to_history(self, invocation: ClaudeInvocation):
        """Add invocation to history with size management."""
        self._invocation_history.append(invocation)
        
        # Keep history size manageable
        if len(self._invocation_history) > self._max_history:
            self._invocation_history = self._invocation_history[-self._max_history:]
    
    def get_invocation_history(self, limit: int = 50) -> List[ClaudeInvocation]:
        """
        Get invocation history for monitoring and debugging.
        
        Args:
            limit: Maximum number of invocations to return
            
        Returns:
            List of ClaudeInvocation objects
        """
        with self._invocation_lock:
            return self._invocation_history[-limit:] if limit else self._invocation_history
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get invocation statistics for monitoring.
        
        Returns:
            Dictionary with invocation statistics
        """
        with self._invocation_lock:
            total_invocations = len(self._invocation_history)
            successful = len([i for i in self._invocation_history if i.result == InvocationResult.SUCCESS])
            failed = len([i for i in self._invocation_history if i.result == InvocationResult.FAILED])
            timeout = len([i for i in self._invocation_history if i.result == InvocationResult.TIMEOUT])
            cancelled = len([i for i in self._invocation_history if i.result == InvocationResult.CANCELLED])
            
            # Calculate average duration for successful invocations
            successful_durations = [i.duration_seconds for i in self._invocation_history 
                                  if i.result == InvocationResult.SUCCESS and i.duration_seconds is not None]
            avg_duration = sum(successful_durations) / len(successful_durations) if successful_durations else 0
            
            stats = {
                "total_invocations": total_invocations,
                "successful_invocations": successful,
                "failed_invocations": failed,
                "timeout_invocations": timeout,
                "cancelled_invocations": cancelled,
                "active_invocations": len(self._active_processes),
                "success_rate": (successful / total_invocations * 100) if total_invocations > 0 else 0,
                "average_duration_seconds": round(avg_duration, 2),
                "timeout_rate": (timeout / total_invocations * 100) if total_invocations > 0 else 0
            }
            
            logger.info(f"📊 Claude Invocation Statistics: {stats}")
            return stats
    
    def cleanup_active_processes(self):
        """
        Cleanup any remaining active processes.
        Should be called during application shutdown.
        """
        with self._invocation_lock:
            if not self._active_processes:
                return
            
            logger.info(f"🧹 Cleaning up {len(self._active_processes)} active Claude processes...")
            
            for invocation_id in list(self._active_processes.keys()):
                success = self.cancel_invocation(invocation_id)
                if success:
                    logger.info(f"✅ Cleaned up process: {invocation_id}")
                else:
                    logger.warning(f"⚠️ Failed to clean up process: {invocation_id}")
            
            logger.info("🧹 Process cleanup completed")