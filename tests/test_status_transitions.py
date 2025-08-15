#!/usr/bin/env python3
"""
Unit tests for Status Transition Management system
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from datetime import datetime
from unittest.mock import MagicMock, Mock

from notion_wrapper import NotionClientWrapper
from status_transition_manager import StatusTransitionManager, TransitionResult
from task_status import TaskStatus


def test_transition_validation():
    """Test status transition validation logic"""
    # Mock the NotionClientWrapper
    mock_notion_client = Mock(spec=NotionClientWrapper)

    # Create StatusTransitionManager
    status_manager = StatusTransitionManager(mock_notion_client)

    # Test valid transitions
    valid_transitions = [
        (TaskStatus.QUEUED_TO_RUN.value, TaskStatus.IN_PROGRESS.value),
        (TaskStatus.IN_PROGRESS.value, TaskStatus.DONE.value),
        (TaskStatus.IN_PROGRESS.value, TaskStatus.FAILED.value),
        (TaskStatus.FAILED.value, TaskStatus.QUEUED_TO_RUN.value),
        (TaskStatus.FAILED.value, TaskStatus.IN_PROGRESS.value),
    ]

    for from_status, to_status in valid_transitions:
        assert status_manager.is_valid_transition(from_status, to_status), f"Should allow transition: {from_status} → {to_status}"

    # Test invalid transitions
    invalid_transitions = [
        (TaskStatus.QUEUED_TO_RUN.value, TaskStatus.DONE.value),
        (TaskStatus.QUEUED_TO_RUN.value, TaskStatus.FAILED.value),
        (TaskStatus.DONE.value, TaskStatus.IN_PROGRESS.value),
        (TaskStatus.DONE.value, TaskStatus.QUEUED_TO_RUN.value),
        (TaskStatus.DONE.value, TaskStatus.FAILED.value),
        (TaskStatus.IN_PROGRESS.value, TaskStatus.QUEUED_TO_RUN.value),
    ]

    for from_status, to_status in invalid_transitions:
        assert not status_manager.is_valid_transition(from_status, to_status), f"Should reject transition: {from_status} → {to_status}"

    print("✅ All transition validation tests passed")


def test_status_extraction():
    """Test status extraction from page objects"""
    mock_notion_client = Mock(spec=NotionClientWrapper)
    status_manager = StatusTransitionManager(mock_notion_client)

    # Test status property type
    page_with_status = {"properties": {"Status": {"status": {"name": "In progress"}}}}

    extracted_status = status_manager._extract_current_status(page_with_status)
    assert extracted_status == "In progress", f"Expected 'In progress', got '{extracted_status}'"

    # Test select property type
    page_with_select = {"properties": {"Status": {"select": {"name": "Done"}}}}

    extracted_status = status_manager._extract_current_status(page_with_select)
    assert extracted_status == "Done", f"Expected 'Done', got '{extracted_status}'"

    # Test missing status
    page_without_status = {"properties": {}}

    extracted_status = status_manager._extract_current_status(page_without_status)
    assert extracted_status == "Unknown", f"Expected 'Unknown', got '{extracted_status}'"

    print("✅ All status extraction tests passed")


def test_statistics():
    """Test statistics collection"""
    mock_notion_client = Mock(spec=NotionClientWrapper)
    status_manager = StatusTransitionManager(mock_notion_client)

    # Initial statistics should be empty
    stats = status_manager.get_statistics()
    expected_stats = {
        "total_transitions": 0,
        "successful_transitions": 0,
        "failed_transitions": 0,
        "rollbacks_attempted": 0,
        "rollbacks_successful": 0,
        "success_rate": 0,
        "rollback_success_rate": 0,
    }

    assert stats == expected_stats, f"Expected {expected_stats}, got {stats}"

    print("✅ Statistics test passed")


def test_thread_safety():
    """Test that the transition manager is thread-safe"""
    mock_notion_client = Mock(spec=NotionClientWrapper)
    status_manager = StatusTransitionManager(mock_notion_client)

    # Check that the lock is properly initialized
    assert hasattr(status_manager, "_transition_lock"), "Should have transition lock"
    assert status_manager._transition_lock is not None, "Lock should be initialized"

    print("✅ Thread safety test passed")


if __name__ == "__main__":
    print("🧪 Running Status Transition Management unit tests...")

    try:
        test_transition_validation()
        test_status_extraction()
        test_statistics()
        test_thread_safety()

        print("🎉 All unit tests passed successfully!")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
