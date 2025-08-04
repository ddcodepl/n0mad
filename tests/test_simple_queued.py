#!/usr/bin/env python3
"""
Test script for the new simple queued processor.
This script demonstrates the new workflow without requiring actual Notion data.
"""

import os
import sys
import json
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_directory_structure():
    """Test that all required directories and files exist."""
    project_root = Path(__file__).parent
    
    print("🔍 Testing directory structure...")
    
    # Check task directory
    task_dir = project_root / "src" / "tasks" / "tasks"
    print(f"📁 Task directory: {task_dir}")
    print(f"   Exists: {'✅' if task_dir.exists() else '❌'}")
    
    if task_dir.exists():
        json_files = list(task_dir.glob("*.json"))
        print(f"   JSON files found: {len(json_files)}")
        for json_file in json_files:
            print(f"      📄 {json_file.name}")
    
    # Check taskmaster directory
    taskmaster_dir = project_root / ".taskmaster" / "tasks"
    print(f"📋 TaskMaster directory: {taskmaster_dir}")
    print(f"   Exists: {'✅' if taskmaster_dir.exists() else '❌'}")
    
    taskmaster_file = taskmaster_dir / "tasks.json"
    print(f"   tasks.json exists: {'✅' if taskmaster_file.exists() else '❌'}")
    
    return task_dir.exists() and taskmaster_dir.exists()

def test_json_file_format():
    """Test that task JSON files have expected format."""
    project_root = Path(__file__).parent
    task_dir = project_root / "src" / "tasks" / "tasks"
    
    print("\n🧪 Testing JSON file format...")
    
    if not task_dir.exists():
        print("❌ Task directory doesn't exist")
        return False
    
    json_files = list(task_dir.glob("*.json"))
    if not json_files:
        print("❌ No JSON files found")
        return False
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            print(f"📄 {json_file.name}: ✅ Valid JSON")
            
            # Check if it has the expected structure
            if isinstance(data, dict) and "master" in data:
                tasks = data.get("master", {}).get("tasks", [])
                print(f"   📋 Contains {len(tasks)} tasks")
            else:
                print(f"   ⚠️  Unexpected structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                
        except json.JSONDecodeError as e:
            print(f"❌ {json_file.name}: Invalid JSON - {e}")
            return False
        except Exception as e:
            print(f"❌ {json_file.name}: Error reading - {e}")
            return False
    
    return True

def test_import_modules():
    """Test that all required modules can be imported."""
    print("\n📦 Testing module imports...")
    
    try:
        from simple_queued_processor import SimpleQueuedProcessor
        print("✅ SimpleQueuedProcessor imported successfully")
        
        from database_operations import DatabaseOperations
        print("✅ DatabaseOperations imported successfully")
        
        from status_transition_manager import StatusTransitionManager
        print("✅ StatusTransitionManager imported successfully")
        
        from task_status import TaskStatus
        print("✅ TaskStatus imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def demonstrate_usage():
    """Demonstrate how to use the new system."""
    print("\n📋 Usage Examples:")
    print("=" * 50)
    
    print("1. Run with the new simple queued mode:")
    print("   uv run main.py --simple-queued")
    print()
    
    print("2. Run directly with the simple processor:")
    print("   python src/simple_queued_processor.py")
    print()
    
    print("3. Test with custom project root:")
    print("   python src/simple_queued_processor.py --project-root /path/to/project")
    print()
    
    print("🔄 New Workflow:")
    print("  1. Check for records with 'Queued to run' status")
    print("  2. Get first record and extract ID")
    print("  3. Look for TASK_DIR/tasks/<TASK_ID>.json")
    print("  4. Copy to ~/.taskmaster/tasks/tasks.json")
    print("  5. Update status to 'In progress'")
    print("  6. Execute Claude Code with predefined prompt")
    print("  7. Update status to 'Done' or 'Failed'")
    print("  8. Process max 1 task at a time")

def main():
    """Run all tests."""
    print("🚀 Testing Simple Queued Processor")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Directory structure
    if test_directory_structure():
        tests_passed += 1
    
    # Test 2: JSON file format
    if test_json_file_format():
        tests_passed += 1
    
    # Test 3: Module imports
    if test_import_modules():
        tests_passed += 1
    
    # Show usage examples
    demonstrate_usage()
    
    # Final results
    print("\n📊 Test Results:")
    print("=" * 50)
    print(f"✅ Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! The new system is ready to use.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the setup.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)