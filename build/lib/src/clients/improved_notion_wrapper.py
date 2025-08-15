"""
Improved Notion client wrapper with proper async patterns, type hints, and error handling.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import aiohttp
from notion_client import AsyncClient as NotionAsyncClient
from notion_client import Client as NotionSyncClient

from ..core.exceptions import ConfigurationError, NotionAPIError, NotionAuthenticationError, NotionRateLimitError, ValidationError
from ..utils.logging_config import get_logger
from ..utils.retry_decorator import notion_api_retry
from ..utils.singleton_config import get_config

logger = get_logger(__name__)


class PropertyType(Enum):
    """Notion property types."""

    SELECT = "select"
    STATUS = "status"
    MULTI_SELECT = "multi_select"
    TITLE = "title"
    RICH_TEXT = "rich_text"
    FILES = "files"
    UNIQUE_ID = "unique_id"


@dataclass
class PageUpdate:
    """Represents a page update operation."""

    page_id: str
    properties: Dict[str, Any]


@dataclass
class BatchResult:
    """Result of a batch operation."""

    successful: List[Dict[str, Any]]
    failed: List[Dict[str, Any]]
    total_processed: int
    success_count: int
    failure_count: int

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_processed == 0:
            return 0.0
        return (self.success_count / self.total_processed) * 100


class ImprovedNotionWrapper:
    """
    Improved Notion client wrapper with proper async patterns,
    comprehensive type hints, and robust error handling.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        database_id: Optional[str] = None,
        max_retries: int = 3,
        rate_limit_per_second: int = 3,
        use_async: bool = True,
    ):
        """
        Initialize Notion client wrapper.

        Args:
            token: Notion API token
            database_id: Notion database ID
            max_retries: Maximum retry attempts
            rate_limit_per_second: API calls per second limit
            use_async: Whether to use async client
        """
        self._config = get_config()
        self.max_retries = max_retries
        self.rate_limit_per_second = rate_limit_per_second
        self.use_async = use_async

        # Initialize credentials
        self._initialize_credentials(token, database_id)

        # Initialize clients
        self._initialize_clients()

        # Cache for database schema
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._property_types_cache: Optional[Dict[str, PropertyType]] = None

    def _initialize_credentials(self, token: Optional[str], database_id: Optional[str]) -> None:
        """Initialize and validate credentials."""
        self.token = token or self._config.get("NOTION_TOKEN")
        if not self.token:
            raise ConfigurationError(
                "Notion token not found. Set NOTION_TOKEN environment variable.",
                error_code="MISSING_TOKEN",
            )

        self.database_id = database_id or self._config.get("NOTION_BOARD_DB")
        if not self.database_id:
            raise ConfigurationError(
                "Notion database ID not found. Set NOTION_BOARD_DB environment variable.",
                error_code="MISSING_DATABASE_ID",
            )

        # Validate credentials format
        if not self._validate_token_format(self.token):
            logger.warning("⚠️ Notion token format appears invalid")

        if not self._validate_database_id_format(self.database_id):
            logger.warning("⚠️ Notion database ID format appears invalid")

    def _initialize_clients(self) -> None:
        """Initialize Notion clients."""
        try:
            if self.use_async:
                self.async_client = NotionAsyncClient(auth=self.token)
                logger.info("✅ Async Notion client initialized")

            # Always initialize sync client for backwards compatibility
            self.sync_client = NotionSyncClient(auth=self.token)
            logger.info("✅ Sync Notion client initialized")

        except Exception as e:
            raise NotionAuthenticationError(f"Failed to initialize Notion client: {e}", error_code="CLIENT_INIT_FAILED") from e

    @staticmethod
    def _validate_token_format(token: str) -> bool:
        """Validate Notion token format."""
        return isinstance(token, str) and len(token) > 40 and (token.startswith("secret_") or len(token) >= 32)

    @staticmethod
    def _validate_database_id_format(db_id: str) -> bool:
        """Validate Notion database ID format."""
        if not isinstance(db_id, str):
            return False

        clean_id = db_id.replace("-", "")
        if len(clean_id) != 32:
            return False

        try:
            int(clean_id, 16)
            return True
        except ValueError:
            return False

    @notion_api_retry
    async def test_connection(self) -> bool:
        """Test connection to Notion API."""
        try:
            if self.use_async:
                database = await self.async_client.databases.retrieve(database_id=self.database_id)
            else:
                database = self.sync_client.databases.retrieve(database_id=self.database_id)

            db_title = self._extract_database_title(database)
            logger.info(f"✅ Successfully connected to database: {db_title}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to Notion database: {e}")
            raise NotionAPIError(f"Connection test failed: {e}") from e

    @staticmethod
    def _extract_database_title(database: Dict[str, Any]) -> str:
        """Extract database title from database object."""
        try:
            title_array = database.get("title", [])
            if title_array and len(title_array) > 0:
                return title_array[0].get("plain_text", "Untitled")
            return "Untitled"
        except (KeyError, IndexError, AttributeError):
            return "Untitled"

    @notion_api_retry
    async def get_database_schema(self) -> Dict[str, Any]:
        """Get database schema with caching."""
        if self._schema_cache is not None:
            return self._schema_cache

        try:
            if self.use_async:
                database = await self.async_client.databases.retrieve(database_id=self.database_id)
            else:
                database = self.sync_client.databases.retrieve(database_id=self.database_id)

            self._schema_cache = database
            self._property_types_cache = self._extract_property_types(database)

            logger.info(f"📋 Database schema cached with {len(database.get('properties', {}))} properties")
            return database

        except Exception as e:
            raise NotionAPIError(f"Failed to retrieve database schema: {e}") from e

    def _extract_property_types(self, database: Dict[str, Any]) -> Dict[str, PropertyType]:
        """Extract property types from database schema."""
        properties = database.get("properties", {})
        property_types = {}

        for prop_name, prop_config in properties.items():
            prop_type_str = prop_config.get("type", "unknown")
            try:
                property_types[prop_name] = PropertyType(prop_type_str)
            except ValueError:
                logger.warning(f"Unknown property type '{prop_type_str}' for property '{prop_name}'")
                continue

        return property_types

    async def get_property_type(self, property_name: str) -> PropertyType:
        """Get property type for a specific property."""
        if self._property_types_cache is None:
            await self.get_database_schema()

        if property_name not in self._property_types_cache:
            raise ValidationError(f"Property '{property_name}' not found in database", field=property_name)

        return self._property_types_cache[property_name]

    async def create_status_filter(self, status_value: str) -> Dict[str, Any]:
        """Create filter for status property based on its type."""
        try:
            status_prop_type = await self.get_property_type("Status")

            filter_mapping = {
                PropertyType.SELECT: {"property": "Status", "select": {"equals": status_value}},
                PropertyType.STATUS: {"property": "Status", "status": {"equals": status_value}},
                PropertyType.MULTI_SELECT: {
                    "property": "Status",
                    "multi_select": {"contains": status_value},
                },
            }

            if status_prop_type not in filter_mapping:
                raise ValidationError(
                    f"Unsupported status property type: {status_prop_type}",
                    field="Status",
                    value=status_prop_type,
                )

            filter_dict = filter_mapping[status_prop_type]
            logger.debug(f"Created status filter: {filter_dict}")
            return filter_dict

        except Exception as e:
            raise NotionAPIError(f"Failed to create status filter: {e}") from e

    @notion_api_retry
    async def query_database(
        self,
        filter_dict: Optional[Dict[str, Any]] = None,
        start_cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Query database with filters and pagination."""
        query_params = {
            "database_id": self.database_id,
            "page_size": min(page_size, 100),  # Notion API limit
        }

        if filter_dict:
            query_params["filter"] = filter_dict
        if start_cursor:
            query_params["start_cursor"] = start_cursor

        try:
            if self.use_async:
                response = await self.async_client.databases.query(**query_params)
            else:
                response = self.sync_client.databases.query(**query_params)

            return response

        except Exception as e:
            raise NotionAPIError(f"Database query failed: {e}") from e

    async def query_pages_by_status(self, status: str, include_all_pages: bool = True) -> List[Dict[str, Any]]:
        """Query pages by status with pagination support."""
        try:
            logger.info(f"🔍 Querying pages with status: '{status}'")

            status_filter = await self.create_status_filter(status)
            all_results = []
            start_cursor = None

            while True:
                response = await self.query_database(filter_dict=status_filter, start_cursor=start_cursor, page_size=100)

                results = response.get("results", [])
                all_results.extend(results)

                logger.debug(f"📄 Retrieved {len(results)} pages in this batch")

                # Check for more pages
                has_more = response.get("has_more", False)
                next_cursor = response.get("next_cursor")

                if not include_all_pages or not has_more or not next_cursor:
                    break

                start_cursor = next_cursor

            logger.info(f"✅ Total pages found with status '{status}': {len(all_results)}")
            return all_results

        except Exception as e:
            raise NotionAPIError(f"Failed to query pages by status '{status}': {e}") from e

    async def update_page_status(self, page_id: str, status: str) -> Dict[str, Any]:
        """Update page status using correct property format."""
        try:
            status_prop_type = await self.get_property_type("Status")

            property_mapping = {
                PropertyType.SELECT: {"Status": {"select": {"name": status}}},
                PropertyType.STATUS: {"Status": {"status": {"name": status}}},
                PropertyType.MULTI_SELECT: {"Status": {"multi_select": [{"name": status}]}},
            }

            if status_prop_type not in property_mapping:
                raise ValidationError(f"Unsupported status property type: {status_prop_type}", field="Status")

            properties = property_mapping[status_prop_type]

            if self.use_async:
                updated_page = await self.async_client.pages.update(page_id=page_id, properties=properties)
            else:
                updated_page = self.sync_client.pages.update(page_id=page_id, properties=properties)

            logger.debug(f"✅ Updated page {page_id[:8]}... status to '{status}'")
            return updated_page

        except Exception as e:
            raise NotionAPIError(f"Failed to update page status: {e}") from e

    async def update_pages_batch(self, updates: List[PageUpdate], max_concurrent: int = 5) -> BatchResult:
        """Update multiple pages concurrently with rate limiting."""
        successful = []
        failed = []

        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(max_concurrent)

        async def update_single_page(update: PageUpdate) -> Dict[str, Any]:
            async with semaphore:
                try:
                    if self.use_async:
                        result = await self.async_client.pages.update(page_id=update.page_id, properties=update.properties)
                    else:
                        result = self.sync_client.pages.update(page_id=update.page_id, properties=update.properties)

                    successful.append({"page_id": update.page_id, "result": result, "status": "success"})

                    return result

                except Exception as e:
                    error_info = {"page_id": update.page_id, "error": str(e), "status": "failed"}
                    failed.append(error_info)
                    logger.error(f"❌ Failed to update page {update.page_id[:8]}...: {e}")
                    raise

        # Execute updates concurrently
        tasks = [update_single_page(update) for update in updates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Error was already logged in update_single_page
                continue

        batch_result = BatchResult(
            successful=successful,
            failed=failed,
            total_processed=len(updates),
            success_count=len(successful),
            failure_count=len(failed),
        )

        logger.info(f"📊 Batch update completed: {batch_result.success_count}/{batch_result.total_processed} successful ({batch_result.success_rate:.1f}%)")

        return batch_result

    def extract_ticket_ids(self, pages: List[Dict[str, Any]]) -> List[str]:
        """Extract ticket IDs from Notion pages."""
        ticket_ids = []

        for page in pages:
            try:
                ticket_id = self._extract_single_ticket_id(page)
                if ticket_id:
                    ticket_ids.append(ticket_id)
                    logger.debug(f"✅ Extracted ticket ID: {ticket_id}")
                else:
                    logger.warning(f"⚠️ Could not extract ticket ID from page {page.get('id', 'unknown')[:8]}...")

            except Exception as e:
                logger.error(f"❌ Error extracting ticket ID from page: {e}")
                continue

        logger.info(f"📊 Extracted {len(ticket_ids)} ticket IDs from {len(pages)} pages")
        return ticket_ids

    def _extract_single_ticket_id(self, page: Dict[str, Any]) -> Optional[str]:
        """Extract ticket ID from a single page."""
        properties = page.get("properties", {})

        # Method 1: Try unique_id property
        if "ID" in properties:
            id_prop = properties["ID"]
            if id_prop.get("type") == "unique_id" and id_prop.get("unique_id"):
                unique_id = id_prop["unique_id"]
                prefix = unique_id.get("prefix", "")
                number = unique_id.get("number", "")
                if prefix and number:
                    return f"{prefix}-{number}"
                elif number:
                    return str(number)

        # Method 2: Try title property with pattern matching
        if "Name" in properties:
            name_prop = properties["Name"]
            if name_prop.get("type") == "title" and name_prop.get("title"):
                title_text = name_prop["title"][0]["plain_text"] if name_prop["title"] else ""
                # Look for pattern like NOMAD-12, TICKET-123
                import re

                match = re.search(r"([A-Z]+-\d+)", title_text)
                if match:
                    return match.group(1)

        # Method 3: Fallback to page ID
        page_id = page.get("id", "")
        if page_id:
            return page_id.replace("-", "")[-8:]

        return None

    async def close(self) -> None:
        """Close async client connections."""
        if hasattr(self, "async_client") and self.async_client:
            try:
                await self.async_client.aclose()
                logger.info("✅ Notion async client closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing async client: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.test_connection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
