#!/usr/bin/env python3
"""
Test script for enhanced DatabaseOperations with query interface, performance monitoring, and caching
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database_operations import DatabaseOperations
from task_status import TaskStatus


class MockNotionClient:
    """Mock Notion client for testing."""

    def __init__(self):
        self.mock_tasks = []
        self.query_count = 0
        self.should_fail = False

    def set_mock_tasks(self, tasks):
        """Set mock tasks to return."""
        self.mock_tasks = tasks

    def set_failure_mode(self, should_fail):
        """Set whether queries should fail."""
        self.should_fail = should_fail

    def create_status_filter(self, status):
        """Mock status filter creation."""
        return {"property": "Status", "select": {"equals": status}}

    def query_database(self, filter=None, page_size=100, start_cursor=None, **kwargs):
        """Mock database query."""
        self.query_count += 1

        if self.should_fail:
            raise Exception("Mock database error")

        # Simulate pagination
        start_index = 0
        if start_cursor:
            start_index = int(start_cursor)

        end_index = min(start_index + page_size, len(self.mock_tasks))
        tasks_slice = self.mock_tasks[start_index:end_index]

        has_more = end_index < len(self.mock_tasks)
        next_cursor = str(end_index) if has_more else None

        return {"results": tasks_slice, "has_more": has_more, "next_cursor": next_cursor}

    def extract_ticket_ids(self, tasks):
        """Mock ticket ID extraction."""
        return [f"TICKET-{task['id'][:8]}" for task in tasks if "id" in task]


def create_mock_task(task_id: str, title: str, status: str) -> dict:
    """Create a mock task for testing."""
    return {
        "id": task_id,
        "url": f"https://notion.so/{task_id}",
        "created_time": "2023-01-01T00:00:00.000Z",
        "last_edited_time": "2023-01-01T00:00:00.000Z",
        "properties": {
            "Name": {"title": [{"plain_text": title}]},
            "Status": {"select": {"name": status}},
        },
    }


def test_basic_functionality():
    """Test basic database operations functionality."""
    print("🧪 Testing basic functionality...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Test initialization
    assert db_ops.notion_client == mock_client
    assert db_ops.query_metrics["total_queries"] == 0

    # Test cache key generation
    cache_key = db_ops._get_cache_key("test_op", param1="value1", param2="value2")
    assert "test_op" in cache_key
    assert "param1=value1" in cache_key
    assert "param2=value2" in cache_key

    print("✅ Basic functionality tests passed")


def test_query_performance_measurement():
    """Test query performance measurement."""
    print("🧪 Testing query performance measurement...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Test successful operation
    with db_ops._measure_query_performance("test_operation"):
        time.sleep(0.1)  # Simulate work

    assert db_ops.query_metrics["total_queries"] == 1
    assert db_ops.query_metrics["successful_queries"] == 1
    assert db_ops.query_metrics["failed_queries"] == 0
    assert db_ops.query_metrics["average_query_time"] > 0.09

    # Test failed operation
    try:
        with db_ops._measure_query_performance("test_failure"):
            time.sleep(0.05)
            raise Exception("Test error")
    except Exception:
        pass

    assert db_ops.query_metrics["total_queries"] == 2
    assert db_ops.query_metrics["successful_queries"] == 1
    assert db_ops.query_metrics["failed_queries"] == 1

    print("✅ Query performance measurement tests passed")


def test_batch_querying():
    """Test batch querying with pagination."""
    print("🧪 Testing batch querying...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Create 150 mock tasks to test pagination
    mock_tasks = []
    for i in range(150):
        mock_tasks.append(create_mock_task(f"task-{i:03d}", f"Task {i}", "Queued to run"))

    mock_client.set_mock_tasks(mock_tasks)

    # Test first batch
    tasks_batch1, cursor1 = db_ops.get_tasks_by_status_batch(TaskStatus.QUEUED_TO_RUN, page_size=50)
    assert len(tasks_batch1) == 50
    assert cursor1 is not None
    assert tasks_batch1[0]["title"] == "Task 0"
    assert tasks_batch1[49]["title"] == "Task 49"

    # Test second batch
    tasks_batch2, cursor2 = db_ops.get_tasks_by_status_batch(TaskStatus.QUEUED_TO_RUN, page_size=50, start_cursor=cursor1)
    assert len(tasks_batch2) == 50
    assert cursor2 is not None
    assert tasks_batch2[0]["title"] == "Task 50"

    # Test final batch
    tasks_batch3, cursor3 = db_ops.get_tasks_by_status_batch(TaskStatus.QUEUED_TO_RUN, page_size=50, start_cursor=cursor2)
    assert len(tasks_batch3) == 50
    assert cursor3 is None  # No more pages

    print("✅ Batch querying tests passed")


def test_get_all_tasks_with_pagination():
    """Test getting all tasks with automatic pagination."""
    print("🧪 Testing get all tasks with automatic pagination...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Create 250 mock tasks
    mock_tasks = []
    for i in range(250):
        mock_tasks.append(create_mock_task(f"task-{i:03d}", f"Task {i}", "Queued to run"))

    mock_client.set_mock_tasks(mock_tasks)

    # Test getting all tasks
    all_tasks = db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=False)
    assert len(all_tasks) == 250
    assert all_tasks[0]["title"] == "Task 0"
    assert all_tasks[249]["title"] == "Task 249"

    # Test with max_tasks limit
    limited_tasks = db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, max_tasks=100, use_cache=False)
    assert len(limited_tasks) == 100

    print("✅ Get all tasks tests passed")


def test_caching_functionality():
    """Test query result caching."""
    print("🧪 Testing caching functionality...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Create mock tasks
    mock_tasks = [create_mock_task("task-001", "Test Task", "Queued to run")]
    mock_client.set_mock_tasks(mock_tasks)

    # First query - should miss cache
    initial_misses = db_ops.query_metrics["cache_misses"]
    initial_hits = db_ops.query_metrics["cache_hits"]

    tasks1 = db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=True)
    assert len(tasks1) == 1
    assert db_ops.query_metrics["cache_misses"] > initial_misses
    assert db_ops.query_metrics["cache_hits"] == initial_hits

    # Second query - should hit cache
    current_misses = db_ops.query_metrics["cache_misses"]
    tasks2 = db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=True)
    assert len(tasks2) == 1
    assert db_ops.query_metrics["cache_misses"] == current_misses  # No new misses
    assert db_ops.query_metrics["cache_hits"] > initial_hits  # Should have hits

    # Test cache clearing
    cleared_count = db_ops.clear_query_cache()
    assert cleared_count > 0

    # Next query should miss cache again
    pre_clear_misses = db_ops.query_metrics["cache_misses"]
    tasks3 = db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=True)
    assert len(tasks3) == 1
    assert db_ops.query_metrics["cache_misses"] > pre_clear_misses

    print("✅ Caching tests passed")


def test_cache_expiration():
    """Test cache entry expiration."""
    print("🧪 Testing cache expiration...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)
    db_ops._cache_ttl = 1  # 1 second TTL for testing

    # Create mock tasks
    mock_tasks = [create_mock_task("task-001", "Test Task", "Queued to run")]
    mock_client.set_mock_tasks(mock_tasks)

    # Query to populate cache
    tasks1 = db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=True)
    assert len(tasks1) == 1

    # Wait for cache to expire
    time.sleep(1.1)

    # Clean up expired entries
    expired_count = db_ops.cleanup_expired_cache()
    assert expired_count > 0

    # Next query should miss cache
    initial_misses = db_ops.query_metrics["cache_misses"]
    tasks2 = db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=True)
    assert db_ops.query_metrics["cache_misses"] > initial_misses

    print("✅ Cache expiration tests passed")


def test_query_metrics():
    """Test query metrics collection."""
    print("🧪 Testing query metrics...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Create mock tasks
    mock_tasks = [create_mock_task("task-001", "Test Task", "Queued to run")]
    mock_client.set_mock_tasks(mock_tasks)

    # Perform several queries
    for _ in range(3):
        db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=False)

    # Test one failure
    mock_client.set_failure_mode(True)
    try:
        db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=False)
    except Exception:
        pass

    mock_client.set_failure_mode(False)

    # Get metrics
    metrics = db_ops.get_query_metrics()

    assert metrics["total_queries"] >= 4
    assert metrics["successful_queries"] >= 3
    assert metrics["failed_queries"] >= 1
    assert 0 < metrics["success_rate"] < 100
    assert metrics["failure_rate"] > 0
    assert "last_query_time" in metrics

    print("✅ Query metrics tests passed")


def test_queue_depth_and_status_distribution():
    """Test queue depth and status distribution methods."""
    print("🧪 Testing queue depth and status distribution...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Create mixed status tasks
    mock_tasks = [
        create_mock_task("task-001", "Queued Task 1", "Queued to run"),
        create_mock_task("task-002", "Queued Task 2", "Queued to run"),
        create_mock_task("task-003", "In Progress Task", "In progress"),
        create_mock_task("task-004", "Done Task", "Done"),
    ]

    # Mock different responses for different statuses
    def mock_query_with_filter(filter=None, **kwargs):
        if filter and "select" in filter and filter["select"].get("equals"):
            status = filter["select"]["equals"]
            filtered_tasks = [task for task in mock_tasks if task["properties"]["Status"]["select"]["name"] == status]
            return {"results": filtered_tasks, "has_more": False, "next_cursor": None}
        return {"results": mock_tasks, "has_more": False, "next_cursor": None}

    mock_client.query_database = mock_query_with_filter

    # Test queue depth
    queue_depth = db_ops.get_queue_depth(use_cache=False)
    assert queue_depth == 2  # Two queued tasks

    # Test status distribution
    distribution = db_ops.get_status_distribution(use_cache=False)
    assert distribution["Queued to run"] == 2
    assert distribution["In progress"] == 1
    assert distribution["Done"] == 1

    print("✅ Queue depth and status distribution tests passed")


def test_backward_compatibility():
    """Test that legacy methods still work."""
    print("🧪 Testing backward compatibility...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Create mock tasks
    mock_tasks = [
        create_mock_task("task-001", "Refine Task", "To Refine"),
        create_mock_task("task-002", "Queued Task", "Queued to run"),
    ]
    mock_client.set_mock_tasks(mock_tasks)

    # Test legacy methods
    refine_tasks = db_ops.get_tasks_to_refine()
    assert len(refine_tasks) >= 0  # Should work without error

    queued_tasks = db_ops.get_queued_tasks()
    assert len(queued_tasks) >= 0  # Should work without error

    has_queued = db_ops.has_queued_tasks()
    assert isinstance(has_queued, bool)

    all_tasks = db_ops.get_all_tasks()
    assert isinstance(all_tasks, list)

    print("✅ Backward compatibility tests passed")


def test_error_handling():
    """Test error handling and resilience."""
    print("🧪 Testing error handling...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Test database failure
    mock_client.set_failure_mode(True)

    try:
        db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=False)
        assert False, "Should have raised an exception"
    except Exception as e:
        assert "Mock database error" in str(e)

    # Test graceful degradation for queue depth
    queue_depth = db_ops.get_queue_depth(use_cache=False)
    assert queue_depth == 0  # Should return 0 on error

    mock_client.set_failure_mode(False)

    print("✅ Error handling tests passed")


def performance_benchmark():
    """Basic performance benchmark."""
    print("🧪 Running performance benchmark...")

    mock_client = MockNotionClient()
    db_ops = DatabaseOperations(mock_client)

    # Create many mock tasks
    mock_tasks = []
    for i in range(1000):
        mock_tasks.append(create_mock_task(f"task-{i:04d}", f"Task {i}", "Queued to run"))

    mock_client.set_mock_tasks(mock_tasks)

    # Benchmark cached vs uncached queries
    start_time = time.time()
    for _ in range(5):
        db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=False)
    uncached_time = time.time() - start_time

    start_time = time.time()
    for _ in range(5):
        db_ops.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=True)
    cached_time = time.time() - start_time

    print(f"   📊 Uncached queries: {uncached_time:.3f}s")
    print(f"   📊 Cached queries: {cached_time:.3f}s")
    print(f"   🚀 Cache speedup: {uncached_time/cached_time:.1f}x")

    # Show metrics
    metrics = db_ops.get_query_metrics()
    print(f"   📈 Total queries: {metrics['total_queries']}")
    print(f"   ✅ Success rate: {metrics['success_rate']:.1f}%")
    print(f"   🎯 Cache hit rate: {metrics['cache_hit_rate']:.1f}%")

    print("✅ Performance benchmark completed")


def main():
    """Run all tests."""
    print("🚀 Starting enhanced DatabaseOperations tests...\n")

    try:
        test_basic_functionality()
        test_query_performance_measurement()
        test_batch_querying()
        test_get_all_tasks_with_pagination()
        test_caching_functionality()
        test_cache_expiration()
        test_query_metrics()
        test_queue_depth_and_status_distribution()
        test_backward_compatibility()
        test_error_handling()
        performance_benchmark()

        print("\n🎉 All enhanced DatabaseOperations tests passed successfully!")
        print("✅ Task Repository Query Interface implementation is working correctly")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
