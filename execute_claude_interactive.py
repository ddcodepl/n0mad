#!/usr/bin/env python3
"""
Interactive Claude Code executor that ensures proper permissions and file modifications.
This script launches Claude Code in a way that guarantees it can modify source files.
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def setup_claude_environment(project_root: Path):
    """Setup the environment for Claude Code execution."""
    print(f"🔧 Setting up Claude Code environment in {project_root}")
    
    # Ensure .claude directory exists
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(exist_ok=True)
    
    # Create or update settings.json with proper permissions
    settings_file = claude_dir / "settings.json"
    settings_content = '''{
  "allowedTools": [
    "Edit",
    "MultiEdit", 
    "Write",
    "Read",
    "Bash",
    "LS",
    "Glob",
    "Grep",
    "TodoWrite",
    "mcp__task_master_ai__*"
  ],
  "autoApprove": true,
  "headless": false,
  "maxTokens": 200000,
  "temperature": 0.1,
  "workingDirectory": "''' + str(project_root) + '''"
}'''
    
    with open(settings_file, 'w') as f:
        f.write(settings_content)
    
    print(f"✅ Created Claude settings at {settings_file}")
    
    # Set proper file permissions
    try:
        os.chmod(project_root, 0o755)
        for root, dirs, files in os.walk(project_root / "src"):
            for dir_name in dirs:
                os.chmod(os.path.join(root, dir_name), 0o755)
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if file_path.endswith(('.py', '.json', '.md', '.txt')):
                    os.chmod(file_path, 0o644)
        print("✅ Set proper file permissions")
    except Exception as e:
        print(f"⚠️ Could not set file permissions: {e}")


def execute_claude_with_instructions(project_root: Path):
    """Execute Claude Code with comprehensive instructions."""
    
    # Change to project directory
    original_cwd = os.getcwd()
    os.chdir(project_root)
    
    try:
        # Comprehensive prompt that ensures file modification
        prompt = """You are working on a Python project. You need to process all tasks from the task master.

CRITICAL INSTRUCTIONS:
1. Use the Task Master AI tools to get the current tasks
2. For each pending task, implement the required functionality by writing or modifying Python files
3. You MUST use the Edit, MultiEdit, or Write tools to make actual changes to source files
4. Do not just analyze or plan - you must implement the code changes
5. Save all changes to disk
6. After implementing each task, update its status to 'done' using task master tools
7. Continue until all tasks are completed

START BY RUNNING: mcp__task_master_ai__get_tasks to see what needs to be done.

Remember: You have full permissions to modify any file in this project. Make the necessary code changes!"""

        print("🚀 Launching Claude Code with task processing instructions...")
        print("=" * 60)
        print("PROMPT:")
        print(prompt)
        print("=" * 60)
        
        # Set environment variables for better behavior
        env = os.environ.copy()
        env.update({
            'CLAUDE_AUTO_APPROVE': 'true',
            'CLAUDE_PROJECT_ROOT': str(project_root),
            'PYTHONPATH': str(project_root / 'src')
        })
        
        # Launch Claude Code interactively
        cmd = ["claude", "-p", prompt]
        print(f"Executing: {' '.join(cmd)}")
        print("⏳ Starting Claude Code (this may take some time)...")
        
        # Use interactive mode to ensure Claude can ask for permissions if needed
        result = subprocess.run(
            cmd,
            cwd=project_root,
            env=env,
            timeout=3600  # 1 hour timeout
        )
        
        print(f"📊 Claude Code finished with exit code: {result.returncode}")
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Claude Code execution timed out after 1 hour")
        return False
    except KeyboardInterrupt:
        print("⏹️ Execution interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Error executing Claude Code: {e}")
        return False
    finally:
        os.chdir(original_cwd)


def main():
    """Main execution function."""
    project_root = Path(__file__).parent
    
    print("🎯 Interactive Claude Code Task Processor")
    print("=" * 50)
    
    # Setup environment
    setup_claude_environment(project_root)
    
    # Wait for user confirmation
    print("\n📋 This will launch Claude Code to process all task master tasks.")
    print("Claude Code will have full permissions to modify source files.")
    
    response = input("\n🤔 Continue? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ Execution cancelled by user")
        return False
    
    # Execute Claude Code
    success = execute_claude_with_instructions(project_root)
    
    if success:
        print("\n✅ Task processing completed successfully!")
        print("💡 Check your source files for the implemented changes.")
    else:
        print("\n❌ Task processing failed or was interrupted.")
        print("💡 You may need to run this script again or check the logs.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)