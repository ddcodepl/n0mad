#!/usr/bin/env python3
"""
Force Claude Code to implement actual code changes instead of just updating task statuses.
This script creates a specialized prompt that requires Claude to modify source files.
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def create_implementation_prompt():
    """Create a generic prompt that works for any project and forces actual implementation."""
    
    prompt = """You are working on a software project that uses Task Master AI for task management.

CRITICAL INSTRUCTIONS - FOLLOW EXACTLY:
1. Use mcp__task_master_ai__get_tasks to see all current tasks
2. Find any tasks with status "pending" or "in-progress"
3. For EACH such task:
   a) Read the task details and requirements carefully  
   b) Implement the required functionality by creating/modifying source files
   c) Use Edit, Write, or MultiEdit tools to make actual code changes
   d) Write real, working code - don't just plan or comment
   e) Save all changes to disk
   f) Only after implementing, use mcp__task_master_ai__set_task_status to mark as done
4. Continue until all tasks are completed
5. Exit when all tasks are done

IMPORTANT: You have full permissions to modify any file. Implement actual working code for each task.
Do not just update task statuses - you must write actual code first."""

    return prompt


def execute_claude_with_forced_implementation(project_root: Path):
    """Execute Claude Code with a prompt that forces actual implementation."""
    
    original_cwd = os.getcwd()
    os.chdir(project_root)
    
    try:
        prompt = create_implementation_prompt()
        
        print("🚀 Launching Claude Code with FORCED IMPLEMENTATION prompt...")
        print("=" * 80)
        print("This prompt specifically prevents Claude from just updating task statuses")
        print("and forces it to write actual code to source files first.")
        print("=" * 80)
        
        # Set environment for maximum permissions and auto-approval
        env = os.environ.copy()
        env.update({
            'CLAUDE_AUTO_APPROVE': 'true',
            'CLAUDE_SKIP_PERMISSIONS': 'true', 
            'CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS': 'true',
            'CLAUDE_PROJECT_ROOT': str(project_root),
            'PYTHONPATH': str(project_root / 'src'),
            'CLAUDE_ALLOW_ALL_TOOLS': 'true',
            'CLAUDE_NO_CONFIRM': 'true'
        })
        
        # Use most permissive command with dangerous skip permissions
        cmd = ["claude", "--dangerously-skip-permissions", "--auto-approve", "-p", prompt]
        
        print(f"Executing: {' '.join(cmd)}")
        print("⏳ Claude Code will now implement actual code changes...")
        
        # Run interactively so user can see what's happening
        result = subprocess.run(
            cmd,
            cwd=project_root,
            env=env
        )
        
        print(f"\n📊 Claude Code finished with exit code: {result.returncode}")
        return result.returncode == 0
        
    except KeyboardInterrupt:
        print("\n⏹️ Execution interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Error executing Claude Code: {e}")
        return False
    finally:
        os.chdir(original_cwd)


def scan_for_changes(project_root: Path):
    """Scan for recent changes in source files."""
    src_dir = project_root / "src"
    
    print("\n🔍 Scanning for recent changes in source files...")
    
    # Check git status if available
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print("📝 Git detected these changes:")
            for line in result.stdout.strip().split('\n'):
                print(f"   {line}")
        else:
            print("⚠️ No git changes detected")
            
    except FileNotFoundError:
        print("ℹ️ Git not available for change detection")
    
    # Check file modification times
    recent_files = []
    import time
    current_time = time.time()
    
    for py_file in src_dir.rglob("*.py"):
        if py_file.is_file():
            mtime = py_file.stat().st_mtime
            # Files modified in last 10 minutes
            if current_time - mtime < 600:
                recent_files.append((py_file, mtime))
    
    if recent_files:
        print(f"\n📁 Recently modified files ({len(recent_files)}):")
        recent_files.sort(key=lambda x: x[1], reverse=True)
        for file_path, mtime in recent_files[:10]:
            rel_path = file_path.relative_to(project_root)
            mod_time = time.strftime("%H:%M:%S", time.localtime(mtime))
            print(f"   {mod_time} - {rel_path}")
    else:
        print("⚠️ No recently modified Python files found")


def main():
    """Main execution function."""
    project_root = Path(__file__).parent
    
    print("⚡ FORCE Claude Code Implementation")
    print("=" * 50)
    print("This will force Claude Code to implement actual code changes")
    print("instead of just updating task statuses.")
    print()
    
    # Show current pending tasks
    print("📋 Checking current task status...")
    try:
        with open(project_root / ".taskmaster" / "tasks" / "tasks.json") as f:
            tasks_data = json.load(f)
        
        pending_tasks = []
        for task in tasks_data.get("master", {}).get("tasks", []):
            if task.get("status") in ["pending", "in-progress"]:
                pending_tasks.append(f"  • {task.get('title', 'Unknown')} ({task.get('status', 'unknown')})")
        
        if pending_tasks:
            print(f"Found {len(pending_tasks)} tasks needing implementation:")
            for task in pending_tasks[:5]:  # Show first 5
                print(task)
            if len(pending_tasks) > 5:
                print(f"  ... and {len(pending_tasks) - 5} more")
        else:
            print("No pending tasks found.")
            return True
            
    except Exception as e:
        print(f"Could not read tasks: {e}")
    
    print("\n🤔 This will launch Claude Code to implement the actual functionality.")
    response = input("Continue? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ Execution cancelled")
        return False
    
    # Execute Claude Code
    success = execute_claude_with_forced_implementation(project_root)
    
    # Scan for changes
    scan_for_changes(project_root)
    
    if success:
        print("\n✅ Forced implementation completed!")
        print("💡 Check the scan results above to see if source files were modified.")
    else:
        print("\n❌ Implementation failed or was interrupted.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)