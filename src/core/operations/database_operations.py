import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.clients.notion_wrapper import NotionClientWrapper
from src.utils.logging_config import get_logger, log_key_value
from src.utils.task_status import TaskStatus

logger = get_logger(__name__)


class DatabaseOperations:
    def __init__(self, notion_client: NotionClientWrapper):
        self.notion_client = notion_client
        self.query_metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_query_time": 0.0,
            "last_query_time": None,
            "cache_hits": 0,
            "cache_misses": 0,
        }
        self._query_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    def _get_cache_key(self, operation: str, **kwargs) -> str:
        """Generate cache key for query results."""
        key_parts = [operation]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        return "|".join(key_parts)

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        if "timestamp" not in cache_entry:
            return False
        age = (datetime.now() - cache_entry["timestamp"]).total_seconds()
        return age < self._cache_ttl

    def _measure_query_performance(self, operation: str):
        """Context manager for measuring query performance."""

        class QueryPerformanceContext:
            def __init__(self, db_ops, operation):
                self.db_ops = db_ops
                self.operation = operation
                self.start_time = None

            def __enter__(self):
                self.start_time = time.time()
                self.db_ops.query_metrics["total_queries"] += 1
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                self.db_ops.query_metrics["last_query_time"] = datetime.now()

                # Update average query time
                total = self.db_ops.query_metrics["total_queries"]
                current_avg = self.db_ops.query_metrics["average_query_time"]
                self.db_ops.query_metrics["average_query_time"] = (current_avg * (total - 1) + duration) / total

                if exc_type is None:
                    self.db_ops.query_metrics["successful_queries"] += 1
                    logger.debug(f"📊 Query '{self.operation}' completed in {duration:.3f}s")
                else:
                    self.db_ops.query_metrics["failed_queries"] += 1
                    logger.warning(f"⚠️ Query '{self.operation}' failed after {duration:.3f}s")

        return QueryPerformanceContext(self, operation)

    def get_tasks_by_status_batch(
        self,
        status: TaskStatus,
        page_size: int = 100,
        start_cursor: Optional[str] = None,
        use_cache: bool = True,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Get tasks by status with pagination support.

        Args:
            status: Task status to filter by
            page_size: Number of tasks to retrieve per page (max 100)
            start_cursor: Pagination cursor for next page
            use_cache: Whether to use caching for performance

        Returns:
            Tuple of (tasks_list, next_cursor) where next_cursor is None if no more pages
        """
        operation = f"get_tasks_by_status_batch_{status.value}"
        cache_key = self._get_cache_key(operation, page_size=page_size, start_cursor=start_cursor)

        # Check cache first if enabled
        if use_cache and cache_key in self._query_cache:
            cache_entry = self._query_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                self.query_metrics["cache_hits"] += 1
                logger.debug(f"📋 Cache hit for {operation}")
                return cache_entry["data"]

        self.query_metrics["cache_misses"] += 1

        with self._measure_query_performance(operation):
            try:
                logger.info(f"🔍 Querying database for tasks with '{status.value}' status (batch: {page_size}, cursor: {start_cursor is not None})")

                # Use dynamic filter creation based on actual property type
                filter_dict = self.notion_client.create_status_filter(status.value)

                # Call query_database with correct parameter names
                response = self.notion_client.query_database(
                    filter_dict=filter_dict,
                    start_cursor=start_cursor,
                    page_size=min(page_size, 100),
                )

                # Extract results and next cursor
                if isinstance(response, dict):
                    tasks = response.get("results", [])
                    next_cursor = response.get("next_cursor")
                    has_more = response.get("has_more", False)

                    if not has_more:
                        next_cursor = None

                    # Process tasks to extract relevant information
                    processed_tasks = self._process_task_list(tasks, status)

                    result = (processed_tasks, next_cursor)

                    # Cache the result if caching is enabled
                    if use_cache:
                        self._query_cache[cache_key] = {"data": result, "timestamp": datetime.now()}

                    log_key_value(
                        logger,
                        f"📊 Found tasks with status '{status.value}'",
                        f"{len(processed_tasks)} (has_more: {has_more})",
                    )

                    return result
                else:
                    logger.warning(f"⚠️ Unexpected response format from database query")
                    return ([], None)

            except Exception as e:
                logger.error(f"❌ Failed to query tasks with status '{status.value}': {e}")
                raise

    def get_tasks_by_status_all(self, status: TaskStatus, max_tasks: Optional[int] = None, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Get all tasks by status with automatic pagination.

        Args:
            status: Task status to filter by
            max_tasks: Maximum number of tasks to retrieve (None for unlimited)
            use_cache: Whether to use caching for performance

        Returns:
            Complete list of tasks with the specified status
        """
        operation = f"get_tasks_by_status_all_{status.value}"
        cache_key = self._get_cache_key(operation, max_tasks=max_tasks)

        # Check cache first if enabled
        if use_cache and cache_key in self._query_cache:
            cache_entry = self._query_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                self.query_metrics["cache_hits"] += 1
                logger.debug(f"📋 Cache hit for {operation}")
                return cache_entry["data"]

        self.query_metrics["cache_misses"] += 1

        with self._measure_query_performance(operation):
            all_tasks = []
            next_cursor = None
            page_count = 0

            while True:
                page_count += 1
                tasks_batch, next_cursor = self.get_tasks_by_status_batch(status, page_size=100, start_cursor=next_cursor, use_cache=False)

                all_tasks.extend(tasks_batch)

                # Check limits
                if max_tasks and len(all_tasks) >= max_tasks:
                    all_tasks = all_tasks[:max_tasks]
                    break

                if not next_cursor:
                    break

                # Safety limit to prevent infinite loops
                if page_count > 100:
                    logger.warning(f"⚠️ Hit page limit (100) for {operation}, stopping pagination")
                    break

            # Cache the complete result if caching is enabled
            if use_cache:
                self._query_cache[cache_key] = {"data": all_tasks, "timestamp": datetime.now()}

            logger.info(f"📊 Retrieved {len(all_tasks)} total tasks with status '{status.value}' in {page_count} pages")
            return all_tasks

    def _process_task_list(self, tasks: List[Dict[str, Any]], status: TaskStatus) -> List[Dict[str, Any]]:
        """
        Process raw task list from Notion API into standardized format.

        Args:
            tasks: Raw task list from Notion API
            status: Expected status for validation

        Returns:
            Processed task list with standardized fields
        """
        processed_tasks = []

        for task in tasks:
            try:
                # Guard against None or invalid task objects
                if task is None:
                    logger.warning("⚠️ Skipping None task in database response")
                    continue

                if not isinstance(task, dict):
                    logger.warning(f"⚠️ Skipping invalid task type: {type(task)}")
                    continue

                if "id" not in task:
                    logger.warning("⚠️ Skipping task without ID field")
                    continue

                task_info = {
                    "id": task["id"],
                    "url": task.get("url", ""),
                    "properties": task.get("properties", {}),
                    "created_time": task.get("created_time", ""),
                    "last_edited_time": task.get("last_edited_time", ""),
                    "status": status.value,  # Ensure status is included
                }

                # Safely extract title
                properties = task.get("properties", {})
                if "Name" in properties and properties["Name"].get("title"):
                    title_list = properties["Name"]["title"]
                    if title_list and len(title_list) > 0:
                        task_info["title"] = title_list[0].get("plain_text", "Untitled")
                    else:
                        task_info["title"] = "Untitled"
                else:
                    task_info["title"] = "Untitled"

                # Extract ticket ID if this is for queued tasks
                if status == TaskStatus.QUEUED_TO_RUN:
                    ticket_ids = self.notion_client.extract_ticket_ids([task])
                    if ticket_ids:
                        task_info["ticket_id"] = ticket_ids[0]
                        logger.debug(f"📄 Found queued task: {task_info['title']} (Ticket: {task_info['ticket_id']})")
                    else:
                        task_info["ticket_id"] = None
                        logger.warning(f"⚠️ Could not extract ticket ID for queued task: {task_info['title']}")

                processed_tasks.append(task_info)

            except Exception as task_error:
                logger.error(f"❌ Error processing individual task: {task_error}")
                continue

        return processed_tasks

    def get_query_metrics(self) -> Dict[str, Any]:
        """Get database query performance metrics."""
        metrics = self.query_metrics.copy()

        # Add calculated metrics
        total_queries = metrics["total_queries"]
        if total_queries > 0:
            metrics["success_rate"] = (metrics["successful_queries"] / total_queries) * 100
            metrics["failure_rate"] = (metrics["failed_queries"] / total_queries) * 100
        else:
            metrics["success_rate"] = 0.0
            metrics["failure_rate"] = 0.0

        # Cache performance
        total_cache_requests = metrics["cache_hits"] + metrics["cache_misses"]
        if total_cache_requests > 0:
            metrics["cache_hit_rate"] = (metrics["cache_hits"] / total_cache_requests) * 100
        else:
            metrics["cache_hit_rate"] = 0.0

        metrics["cache_size"] = len(self._query_cache)

        # Convert datetime to ISO string for JSON serialization
        if metrics["last_query_time"]:
            metrics["last_query_time"] = metrics["last_query_time"].isoformat()

        return metrics

    def clear_query_cache(self) -> int:
        """Clear the query cache and return number of entries cleared."""
        cache_size = len(self._query_cache)
        self._query_cache.clear()
        logger.info(f"🧹 Cleared query cache ({cache_size} entries)")
        return cache_size

    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries and return number of entries removed."""
        expired_keys = []
        now = datetime.now()

        for key, entry in self._query_cache.items():
            if "timestamp" in entry:
                age = (now - entry["timestamp"]).total_seconds()
                if age >= self._cache_ttl:
                    expired_keys.append(key)

        for key in expired_keys:
            del self._query_cache[key]

        if expired_keys:
            logger.info(f"🧹 Removed {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def get_queue_depth(self, use_cache: bool = True) -> int:
        """
        Get the current queue depth (number of tasks with QUEUED_TO_RUN status).

        Args:
            use_cache: Whether to use caching for performance

        Returns:
            Number of queued tasks
        """
        try:
            queued_tasks = self.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=use_cache)
            return len(queued_tasks)
        except Exception as e:
            logger.error(f"❌ Failed to get queue depth: {e}")
            return 0

    def get_status_distribution(self, use_cache: bool = True) -> Dict[str, int]:
        """
        Get the distribution of tasks across all status values.

        Args:
            use_cache: Whether to use caching for performance

        Returns:
            Dictionary mapping status names to task counts
        """
        distribution = {}

        for status in TaskStatus:
            try:
                tasks = self.get_tasks_by_status_all(status, use_cache=use_cache)
                distribution[status.value] = len(tasks)
            except Exception as e:
                logger.error(f"❌ Failed to get count for status '{status.value}': {e}")
                distribution[status.value] = 0

        return distribution

    def get_tasks_to_refine(self) -> List[Dict[str, Any]]:
        """Get tasks with 'To Refine' status using enhanced query infrastructure."""
        logger.info("🔍 Polling database for tasks with 'To Refine' status...")
        return self.get_tasks_by_status_all(TaskStatus.TO_REFINE, use_cache=True)

    def get_task_by_status(self, status: TaskStatus) -> List[Dict[str, Any]]:
        """Get tasks by status using enhanced query infrastructure (legacy method)."""
        logger.info(f"🔍 Querying database for tasks with '{status.value}' status...")
        # Return raw tasks for backward compatibility
        processed_tasks = self.get_tasks_by_status_all(status, use_cache=True)
        # Convert back to raw format by extracting original task data
        raw_tasks = []
        for task in processed_tasks:
            raw_task = {
                "id": task["id"],
                "url": task.get("url", ""),
                "properties": task.get("properties", {}),
                "created_time": task.get("created_time", ""),
                "last_edited_time": task.get("last_edited_time", ""),
            }
            raw_tasks.append(raw_task)

        log_key_value(logger, f"📊 Found tasks with status '{status.value}'", str(len(raw_tasks)))
        return raw_tasks

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks using enhanced query infrastructure (legacy method)."""
        logger.info("🔍 Retrieving all tasks from database...")
        with self._measure_query_performance("get_all_tasks"):
            try:
                response = self.notion_client.query_database()

                # Extract results from the response
                tasks = response.get("results", []) if isinstance(response, dict) else []
                log_key_value(logger, "📊 Retrieved total tasks", str(len(tasks)))
                return tasks
            except Exception as e:
                logger.error(f"❌ Failed to retrieve all tasks: {e}")
                raise

    def get_queued_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all tickets with 'Queued to run' status using enhanced query infrastructure.

        Returns:
            List of ticket dictionaries with ID, properties, and metadata
        """
        logger.info("🔍 Detecting tickets with 'Queued to run' status...")

        try:
            # Use the enhanced query method for better performance
            processed_tasks = self.get_tasks_by_status_all(TaskStatus.QUEUED_TO_RUN, use_cache=True)

            log_key_value(logger, "📊 Queued tasks detected", str(len(processed_tasks)))

            if processed_tasks:
                logger.info("✅ Found queued tasks ready for processing:")
                for task in processed_tasks:
                    ticket_display = task.get("ticket_id", "No ID")
                    logger.info(f"   🎯 {task['title']} (Ticket: {ticket_display})")
            else:
                logger.info("ℹ️  No tasks found with 'Queued to run' status")

            return processed_tasks

        except Exception as e:
            logger.error(f"❌ Failed to detect queued tasks: {e}")
            raise

    def has_queued_tasks(self) -> bool:
        """
        Check if there are any tickets with 'Queued to run' status.
        Uses optimized queue depth method for better performance.

        Returns:
            True if there are queued tasks, False otherwise
        """
        try:
            queue_depth = self.get_queue_depth(use_cache=True)
            has_tasks = queue_depth > 0
            logger.info(f"🔍 Queued task check result: {'Tasks found' if has_tasks else 'No tasks found'} (depth: {queue_depth})")
            return has_tasks
        except Exception as e:
            logger.error(f"❌ Failed to check for queued tasks: {e}")
            return False
