"""
Comprehensive tests for improved components.
"""

import asyncio
import json

# Import the components we're testing
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clients.improved_notion_wrapper import ImprovedNotionWrapper, PropertyType
from core.exceptions import ConfigurationError, NomadError, NotionAPIError, NotionRateLimitError, ProcessingError, ValidationError
from core.processors.prepare_mode_processor import PrepareTasksProcessor
from utils.performance_profiler import PerformanceProfiler, profile_operation
from utils.retry_decorator import notion_api_retry, retry_with_backoff
from utils.singleton_config import SingletonConfigManager, get_config, initialize_config
from utils.typed_config import APIKeyValidator, APIProvider, BooleanValidator, IntegerValidator, PathValidator, StringValidator


class TestExceptionHierarchy:
    """Test custom exception hierarchy."""

    def test_nomad_error_base(self):
        """Test base NomadError functionality."""
        error = NomadError("Test message", error_code="TEST_001", details={"key": "value"})
        assert str(error) == "Test message"
        assert error.error_code == "TEST_001"
        assert error.details == {"key": "value"}

    def test_configuration_error(self):
        """Test ConfigurationError inheritance."""
        error = ConfigurationError("Config missing")
        assert isinstance(error, NomadError)
        assert str(error) == "Config missing"

    def test_notion_api_error(self):
        """Test NotionAPIError with status code."""
        error = NotionAPIError("API failed", status_code=500)
        assert error.status_code == 500
        assert isinstance(error, NomadError)

    def test_notion_rate_limit_error(self):
        """Test NotionRateLimitError with retry info."""
        error = NotionRateLimitError("Rate limited", retry_after=60)
        assert error.retry_after == 60
        assert error.status_code == 429

    def test_validation_error(self):
        """Test ValidationError with field info."""
        error = ValidationError("Invalid value", field="email", value="invalid_email")
        assert error.field == "email"
        assert error.value == "invalid_email"


class TestSingletonConfig:
    """Test singleton configuration manager."""

    def teardown_method(self):
        """Reset singleton after each test."""
        SingletonConfigManager.reset()

    def test_singleton_pattern(self):
        """Test that singleton returns same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_initialize_with_parameters(self):
        """Test initialization with specific parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = initialize_config(working_dir=temp_dir, strict_validation=False)
            assert config.working_dir == Path(temp_dir)
            assert not config.strict_validation

    @patch.dict("os.environ", {"NOTION_TOKEN": "secret_test_token", "NOTION_BOARD_DB": "a" * 32})
    def test_config_with_env_vars(self):
        """Test configuration loading from environment variables."""
        config = initialize_config(strict_validation=False)
        assert config.get("NOTION_TOKEN") == "secret_test_token"
        assert config.get("NOTION_BOARD_DB") == "a" * 32


class TestTypedValidators:
    """Test typed configuration validators."""

    def test_string_validator(self):
        """Test string validator functionality."""
        validator = StringValidator(min_length=5, max_length=10, pattern=r"^test_.*")

        assert validator.validate("test_abc")
        assert not validator.validate("test")  # Too short
        assert not validator.validate("test_toolongvalue")  # Too long
        assert not validator.validate("abc_test")  # Doesn't match pattern
        assert not validator.validate(123)  # Not a string

    def test_integer_validator(self):
        """Test integer validator functionality."""
        validator = IntegerValidator(min_value=1, max_value=100)

        assert validator.validate(50)
        assert validator.validate("75")  # String that can be converted
        assert not validator.validate(0)  # Below minimum
        assert not validator.validate(101)  # Above maximum
        assert not validator.validate("not_a_number")

    def test_boolean_validator(self):
        """Test boolean validator functionality."""
        validator = BooleanValidator()

        assert validator.validate(True)
        assert validator.validate(False)
        assert validator.validate("true")
        assert validator.validate("false")
        assert validator.validate("1")
        assert validator.validate("0")
        assert validator.validate("yes")
        assert validator.validate("no")
        assert not validator.validate("maybe")
        assert not validator.validate(123)

    def test_path_validator(self):
        """Test path validator functionality."""
        validator = PathValidator(must_exist=False, must_be_writable=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test_file.txt"
            assert validator.validate(str(temp_path))
            assert validator.validate(temp_path)

            # Test non-existent parent directory
            bad_path = Path("/nonexistent/path/file.txt")
            assert not validator.validate(str(bad_path))

    def test_api_key_validator(self):
        """Test API key validator functionality."""
        openai_validator = APIKeyValidator(APIProvider.OPENAI)
        anthropic_validator = APIKeyValidator(APIProvider.ANTHROPIC)

        # Valid OpenAI key format
        assert openai_validator.validate("sk-" + "a" * 45)
        assert not openai_validator.validate("invalid_key")
        assert not openai_validator.validate("your_key_here")

        # Valid Anthropic key format
        assert anthropic_validator.validate("sk-ant-" + "a" * 45)
        assert not anthropic_validator.validate("sk-" + "a" * 45)  # Wrong format


class TestRetryDecorator:
    """Test retry decorator functionality."""

    def test_successful_function(self):
        """Test that successful functions work normally."""

        @retry_with_backoff(max_retries=3)
        def successful_function(value):
            return value * 2

        result = successful_function(5)
        assert result == 10

    def test_retry_on_exception(self):
        """Test retry behavior with exceptions."""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.1)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = failing_function()
        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Test behavior when max retries is exceeded."""

        @retry_with_backoff(max_retries=2, base_delay=0.1)
        def always_failing_function():
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_failing_function()

    @pytest.mark.asyncio
    async def test_async_retry(self):
        """Test retry with async functions."""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.1)
        async def async_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Async failure")
            return "async_success"

        result = await async_failing_function()
        assert result == "async_success"
        assert call_count == 2


class TestImprovedNotionWrapper:
    """Test improved Notion wrapper functionality."""

    @pytest.fixture
    def mock_notion_client(self):
        """Mock Notion client for testing."""
        mock_client = Mock()
        mock_client.databases.retrieve.return_value = {
            "title": [{"plain_text": "Test Database"}],
            "properties": {
                "Status": {
                    "type": "status",
                    "status": {
                        "options": [
                            {"name": "Prepare Tasks", "color": "blue"},
                            {"name": "Ready to Run", "color": "green"},
                        ]
                    },
                }
            },
        }
        return mock_client

    @patch("clients.improved_notion_wrapper.get_config")
    @patch("clients.improved_notion_wrapper.NotionSyncClient")
    def test_initialization(self, mock_sync_client, mock_get_config):
        """Test proper initialization of ImprovedNotionWrapper."""
        # Mock configuration
        mock_config = Mock()
        mock_config.get.side_effect = lambda key: {
            "NOTION_TOKEN": "secret_test_token",
            "NOTION_BOARD_DB": "a" * 32,
        }.get(key)
        mock_get_config.return_value = mock_config

        wrapper = ImprovedNotionWrapper(use_async=False)

        assert wrapper.token == "secret_test_token"
        assert wrapper.database_id == "a" * 32
        assert wrapper.max_retries == 3
        mock_sync_client.assert_called_once()

    def test_property_type_classification(self):
        """Test property type classification."""
        wrapper = ImprovedNotionWrapper.__new__(ImprovedNotionWrapper)

        database_schema = {
            "properties": {
                "Status": {"type": "status"},
                "Tags": {"type": "multi_select"},
                "Name": {"type": "title"},
                "Notes": {"type": "rich_text"},
            }
        }

        property_types = wrapper._extract_property_types(database_schema)

        assert property_types["Status"] == PropertyType.STATUS
        assert property_types["Tags"] == PropertyType.MULTI_SELECT
        assert property_types["Name"] == PropertyType.TITLE
        assert property_types["Notes"] == PropertyType.RICH_TEXT

    def test_ticket_id_extraction(self):
        """Test ticket ID extraction from pages."""
        wrapper = ImprovedNotionWrapper.__new__(ImprovedNotionWrapper)

        pages = [
            {
                "id": "page-id-1",
                "properties": {"ID": {"type": "unique_id", "unique_id": {"prefix": "NOMAD", "number": 123}}},
            },
            {
                "id": "page-id-2",
                "properties": {
                    "Name": {
                        "type": "title",
                        "title": [{"plain_text": "TICKET-456 Feature Request"}],
                    }
                },
            },
        ]

        ticket_ids = wrapper.extract_ticket_ids(pages)

        assert "NOMAD-123" in ticket_ids
        assert "TICKET-456" in ticket_ids


class TestPrepareTasksProcessor:
    """Test prepare tasks processor functionality."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for processor."""
        mock_notion_client = Mock()
        mock_cmd_executor = Mock()
        mock_file_ops = Mock()

        return {
            "notion_client": mock_notion_client,
            "cmd_executor": mock_cmd_executor,
            "file_ops": mock_file_ops,
            "project_root": "/test/project",
        }

    def test_processor_initialization(self, mock_dependencies):
        """Test processor initialization."""
        processor = PrepareTasksProcessor(**mock_dependencies)

        assert processor.notion_client == mock_dependencies["notion_client"]
        assert processor.cmd_executor == mock_dependencies["cmd_executor"]
        assert processor.file_ops == mock_dependencies["file_ops"]
        assert processor.project_root == "/test/project"

    def test_no_tasks_found_handling(self, mock_dependencies):
        """Test handling when no tasks are found."""
        mock_dependencies["notion_client"].query_tickets_by_status.return_value = []

        processor = PrepareTasksProcessor(**mock_dependencies)
        result = processor.process_prepare_tasks()

        assert result["summary"]["message"] == "No tickets to process"
        assert result["summary"]["total_tickets"] == 0
        assert not result["overall_success"]

    def test_successful_workflow(self, mock_dependencies):
        """Test successful workflow execution."""
        # Mock successful responses
        mock_dependencies["notion_client"].query_tickets_by_status.return_value = [{"id": "page-1", "properties": {}}]
        mock_dependencies["notion_client"].extract_ticket_ids.return_value = ["TICKET-1"]
        mock_dependencies["file_ops"].validate_task_files.return_value = ["TICKET-1"]
        mock_dependencies["notion_client"].update_tickets_status_batch.return_value = {"success_count": 1}
        mock_dependencies["cmd_executor"].execute_taskmaster_command.return_value = {
            "successful_executions": [{"ticket_id": "TICKET-1"}],
            "failed_executions": [],
        }
        mock_dependencies["file_ops"].copy_tasks_file.return_value = {"success": True}
        mock_dependencies["notion_client"].upload_tasks_files_to_pages.return_value = {
            "successful_uploads": [{"ticket_id": "TICKET-1", "page_id": "page-1", "file_path": "/path"}]
        }
        mock_dependencies["notion_client"].finalize_ticket_status.return_value = {
            "success_count": 1,
            "finalized_tickets": [{"ticket_id": "TICKET-1"}],
            "failed_finalizations": [],
        }

        processor = PrepareTasksProcessor(**mock_dependencies)
        result = processor.process_prepare_tasks()

        assert result["overall_success"]
        assert result["summary"]["successful_tickets"] == 1
        assert result["summary"]["failed_tickets"] == 0


class TestPerformanceProfiler:
    """Test performance profiler functionality."""

    def test_profiler_initialization(self):
        """Test profiler initialization."""
        profiler = PerformanceProfiler(max_history=500)
        assert profiler.max_history == 500
        assert len(profiler.metrics) == 0

    def test_profile_operation_decorator(self):
        """Test profile operation decorator."""
        profiler = PerformanceProfiler()

        @profiler.profile_function("test_operation")
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)
        assert result == 5
        assert len(profiler.metrics) == 1
        assert profiler.metrics[0].name == "test_operation"

    def test_profile_context_manager(self):
        """Test profile context manager."""
        profiler = PerformanceProfiler()

        with profiler.profile_operation("context_test"):
            result = sum(range(1000))

        assert len(profiler.metrics) == 1
        assert profiler.metrics[0].name == "context_test"
        assert profiler.metrics[0].duration > 0

    def test_aggregated_metrics(self):
        """Test aggregated metrics calculation."""
        profiler = PerformanceProfiler()

        # Record multiple operations with same name
        for i in range(5):
            with profiler.profile_operation("repeated_op"):
                pass

        aggregated = profiler.get_aggregated_metrics("repeated_op")
        assert "repeated_op" in aggregated
        assert aggregated["repeated_op"].call_count == 5
        assert aggregated["repeated_op"].avg_duration > 0

    def test_slow_operations_detection(self):
        """Test detection of slow operations."""
        profiler = PerformanceProfiler()

        # Mock a slow operation
        import time

        with profiler.profile_operation("slow_op"):
            time.sleep(0.1)  # 100ms operation

        slow_ops = profiler.get_slow_operations(threshold=0.05)  # 50ms threshold
        assert len(slow_ops) == 1
        assert slow_ops[0].name == "slow_op"


# Integration tests
class TestIntegration:
    """Integration tests for improved components."""

    @pytest.mark.asyncio
    async def test_async_notion_wrapper_integration(self):
        """Test async notion wrapper with retry decorator."""
        # This would require actual Notion API credentials in a real test
        # For now, we'll mock the behavior

        with patch("clients.improved_notion_wrapper.NotionAsyncClient") as mock_async_client:
            mock_client_instance = AsyncMock()
            mock_async_client.return_value = mock_client_instance

            # Mock successful database retrieval
            mock_client_instance.databases.retrieve.return_value = {
                "title": [{"plain_text": "Test DB"}],
                "properties": {"Status": {"type": "status"}},
            }

            # Mock config
            with patch("clients.improved_notion_wrapper.get_config") as mock_config:
                mock_config_instance = Mock()
                mock_config_instance.get.side_effect = lambda key: {
                    "NOTION_TOKEN": "secret_test",
                    "NOTION_BOARD_DB": "a" * 32,
                }.get(key)
                mock_config.return_value = mock_config_instance

                wrapper = ImprovedNotionWrapper(use_async=True)

                # Test connection
                result = await wrapper.test_connection()
                assert result is True

    def test_config_and_validation_integration(self):
        """Test configuration with validation integration."""
        # Reset singleton
        SingletonConfigManager.reset()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "NOTION_TOKEN": "secret_valid_token_for_testing",
                    "NOTION_BOARD_DB": "a" * 32,
                    "NOMAD_MAX_CONCURRENT_TASKS": "5",
                },
            ):
                config = initialize_config(working_dir=temp_dir, strict_validation=False)

                # Test validators
                from utils.typed_config import IntegerValidator

                validator = IntegerValidator(min_value=1, max_value=20)

                concurrent_tasks = config.get("NOMAD_MAX_CONCURRENT_TASKS")
                assert validator.validate(concurrent_tasks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
