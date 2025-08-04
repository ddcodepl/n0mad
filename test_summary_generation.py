#!/usr/bin/env python3
"""
Test script to demonstrate the task summary generation functionality.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from simple_queued_processor import SimpleQueuedProcessor


def test_summary_generation():
    """Test the summary generation functionality."""
    project_root = Path(__file__).parent
    
    print("🧪 Testing Task Summary Generation")
    print("=" * 50)
    
    # Initialize processor
    try:
        processor = SimpleQueuedProcessor(str(project_root))
        print("✅ Processor initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return False
    
    # Create a mock task for testing
    mock_task = {
        "id": "test-page-id",
        "ticket_id": "TEST-123",
        "title": "Test Task Implementation",
        "status": "Queued to run"
    }
    
    print(f"\n📋 Testing with mock task: {mock_task['title']}")
    
    # Test summary generation
    try:
        processor._generate_task_summary(mock_task)
        print("✅ Summary generation completed")
        
        # Check if summary file was created
        summary_file = project_root / "src" / "tasks" / "summary" / f"{mock_task['ticket_id']}.md"
        if summary_file.exists():
            print(f"✅ Summary file created: {summary_file}")
            print(f"📏 File size: {summary_file.stat().st_size} bytes")
            
            # Show first few lines
            with open(summary_file, 'r') as f:
                lines = f.readlines()
                print(f"📄 First 5 lines of summary:")
                for i, line in enumerate(lines[:5], 1):
                    print(f"   {i}: {line.rstrip()}")
            
            return True
        else:
            print(f"❌ Summary file not found: {summary_file}")
            return False
            
    except Exception as e:
        print(f"❌ Summary generation failed: {e}")
        return False


def main():
    """Main test function."""
    print("🚀 Task Summary Generation Test")
    print("This script tests the automatic generation of task summaries")
    print()
    
    success = test_summary_generation()
    
    print("\n📊 Test Results:")
    if success:
        print("✅ All tests passed!")
        print("🎉 Summary generation is working correctly")
        print("\n📁 Check the src/tasks/summary/ directory for generated files")
    else:
        print("❌ Tests failed!")
        print("🔧 Check the error messages above for troubleshooting")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)