# Notion API Integration

The Notion API integration provides comprehensive access to Notion databases and pages for task management and automation.

## Overview

The `NotionClientWrapper` class provides a high-level interface to the Notion API with built-in error handling, retry logic, and security features.

## Quick Start

```python
from nomad.clients.notion_wrapper import NotionClientWrapper

# Initialize client (uses environment variables)
notion = NotionClientWrapper()

# Test connection
if notion.test_connection():
    print("✅ Connected to Notion successfully")
else:
    print("❌ Failed to connect to Notion")
```

## Authentication

### Required Environment Variables

```env
# Notion integration token
NOTION_TOKEN=secret_your_notion_integration_token

# Target database ID
NOTION_BOARD_DB=your_notion_database_id_here
```

### Getting API Credentials

1. **Create Notion Integration**:
   - Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Name it (e.g., "Nomad Automation")
   - Select workspace and capabilities
   - Copy the "Internal Integration Token"

2. **Share Database**:
   - Open your Notion database
   - Click "Share" in the top-right
   - Invite your integration by name
   - Grant "Can edit" permissions

3. **Get Database ID**:
   - Copy your database URL
   - Extract the 32-character ID from the URL
   - Format: `https://notion.so/workspace/DATABASE_ID?v=...`

## Class Reference

### NotionClientWrapper

Main class for Notion API operations.

#### Constructor

```python
def __init__(
    self,
    token: Optional[str] = None,
    database_id: Optional[str] = None,
    max_retries: int = 3
) -> None
```

**Parameters:**
- `token` (optional): Notion API token. If None, uses `NOTION_TOKEN` environment variable
- `database_id` (optional): Database ID. If None, uses `NOTION_BOARD_DB` environment variable
- `max_retries`: Maximum retry attempts for failed API calls

**Example:**
```python
# Using environment variables (recommended)
notion = NotionClientWrapper()

# Using explicit parameters
notion = NotionClientWrapper(
    token="secret_abc123",
    database_id="d4f2a1b8c5e7",
    max_retries=5
)
```

## Core Methods

### Connection and Validation

#### test_connection()

Tests the connection to Notion API and validates permissions.

```python
def test_connection(self) -> bool
```

**Returns:** `True` if connection successful, `False` otherwise

**Example:**
```python
if notion.test_connection():
    print("Connection successful")
else:
    print("Connection failed - check credentials and permissions")
```

#### debug_database_schema()

Retrieves and analyzes the database schema for debugging.

```python
def debug_database_schema(self) -> Dict[str, Any]
```

**Returns:** Dictionary containing database schema information

**Example:**
```python
schema = notion.debug_database_schema()
print(f"Database title: {schema['title']}")
print(f"Properties: {list(schema['properties'].keys())}")
```

### Database Operations

#### query_database()

Performs a filtered query on the Notion database.

```python
def query_database(
    self,
    filter_dict: Optional[Dict[str, Any]] = None,
    start_cursor: Optional[str] = None,
    page_size: int = 100
) -> Dict[str, Any]
```

**Parameters:**
- `filter_dict`: Notion filter object (see [Notion Filter Documentation](https://developers.notion.com/reference/post-database-query-filter))
- `start_cursor`: Pagination cursor for continued queries
- `page_size`: Number of results per page (max 100)

**Returns:** Dictionary with query results and pagination info

**Example:**
```python
# Query all pages
results = notion.query_database()

# Query with filter
filter_obj = {
    "property": "Status",
    "status": {
        "equals": "To Refine"
    }
}
filtered_results = notion.query_database(filter_dict=filter_obj)

# Paginated query
page1 = notion.query_database(page_size=10)
if page1.get("has_more"):
    page2 = notion.query_database(
        start_cursor=page1["next_cursor"],
        page_size=10
    )
```

#### query_tickets_by_status()

Convenience method to query pages by status property.

```python
def query_tickets_by_status(
    self,
    status: str,
    include_all_pages: bool = True
) -> List[Dict[str, Any]]
```

**Parameters:**
- `status`: Status value to filter by (e.g., "To Refine", "In Progress")
- `include_all_pages`: Whether to fetch all pages with pagination

**Returns:** List of page objects matching the status

**Example:**
```python
# Get all "To Refine" tasks
refine_tasks = notion.query_tickets_by_status("To Refine")
print(f"Found {len(refine_tasks)} tasks to refine")

# Get first page only
first_page = notion.query_tickets_by_status("In Progress", include_all_pages=False)
```

### Page Operations

#### get_page()

Retrieves a specific page by ID.

```python
def get_page(self, page_id: str) -> Dict[str, Any]
```

**Parameters:**
- `page_id`: Notion page ID (32-character string)

**Returns:** Page object with properties and metadata

**Example:**
```python
page = notion.get_page("d4f2a1b8-c5e7-4321-9876-543210fedcba")
print(f"Page title: {page['properties']['Name']['title'][0]['plain_text']}")
```

#### update_page()

Updates page properties.

```python
def update_page(self, page_id: str, properties: Dict[str, Any]) -> Dict[str, Any]
```

**Parameters:**
- `page_id`: Page ID to update
- `properties`: Properties to update (Notion property format)

**Returns:** Updated page object

**Example:**
```python
# Update status and add comment
properties = {
    "Status": {
        "status": {
            "name": "In Progress"
        }
    },
    "Comments": {
        "rich_text": [
            {
                "text": {
                    "content": "Started processing this task"
                }
            }
        ]
    }
}

updated_page = notion.update_page(page_id, properties)
```

#### update_page_status()

Convenience method to update only the status property.

```python
def update_page_status(self, page_id: str, status: str) -> Dict[str, Any]
```

**Parameters:**
- `page_id`: Page ID to update
- `status`: New status value

**Returns:** Updated page object

**Example:**
```python
# Mark task as completed
notion.update_page_status(page_id, "Done")

# Mark task as failed
notion.update_page_status(page_id, "Failed")
```

### Content Operations

#### get_page_content()

Retrieves the content blocks from a page.

```python
def get_page_content(self, page_id: str) -> str
```

**Parameters:**
- `page_id`: Page ID to get content from

**Returns:** Plain text content of the page

**Example:**
```python
content = notion.get_page_content(page_id)
print(f"Page content:\n{content}")
```

#### update_page_content()

Updates the content of a page with new blocks.

```python
def update_page_content(
    self,
    page_id: str,
    content: str,
    status: str = None,
    shutdown_flag: callable = None
) -> None
```

**Parameters:**
- `page_id`: Page ID to update
- `content`: New content (markdown format)
- `status`: Optional status to set simultaneously
- `shutdown_flag`: Function that returns True if operation should be cancelled

**Example:**
```python
new_content = """
# Updated Task Content

## Summary
This task has been processed and updated.

## Next Steps
- Review the changes
- Test the implementation
- Deploy to production

## Notes
Processing completed at {datetime.now()}
"""

notion.update_page_content(
    page_id=page_id,
    content=new_content,
    status="Review"
)
```

### Batch Operations

#### update_tickets_status_batch()

Updates status for multiple pages in a single operation.

```python
def update_tickets_status_batch(
    self,
    page_ids: List[str],
    new_status: str
) -> Dict[str, Any]
```

**Parameters:**
- `page_ids`: List of page IDs to update
- `new_status`: Status to set for all pages

**Returns:** Dictionary with success/failure counts and details

**Example:**
```python
page_ids = ["page1", "page2", "page3"]
result = notion.update_tickets_status_batch(page_ids, "In Progress")

print(f"Updated {result['success_count']} pages")
if result['failed_updates']:
    print(f"Failed to update: {result['failed_updates']}")
```

### File Operations

#### upload_tasks_files_to_pages()

Uploads files to the "Tasks" property of multiple pages.

```python
def upload_tasks_files_to_pages(
    self,
    ticket_data_with_files: List[Dict[str, Any]]
) -> Dict[str, Any]
```

**Parameters:**
- `ticket_data_with_files`: List of dictionaries with ticket_id, page_id, and tasks_file_path

**Returns:** Dictionary with upload results

**Example:**
```python
upload_data = [
    {
        "ticket_id": "TASK-123",
        "page_id": "page_id_123",
        "tasks_file_path": "/path/to/tasks.json"
    },
    {
        "ticket_id": "TASK-124",
        "page_id": "page_id_124",
        "tasks_file_path": "/path/to/tasks2.json"
    }
]

result = notion.upload_tasks_files_to_pages(upload_data)
print(f"Uploaded {len(result['successful_uploads'])} files")
```

## Utility Methods

### extract_ticket_ids()

Extracts ticket IDs from page objects.

```python
def extract_ticket_ids(self, pages: List[Dict[str, Any]]) -> List[str]
```

**Parameters:**
- `pages`: List of page objects from query results

**Returns:** List of ticket ID strings

**Example:**
```python
pages = notion.query_tickets_by_status("To Refine")
ticket_ids = notion.extract_ticket_ids(pages)
print(f"Found tickets: {ticket_ids}")
```

## Error Handling

The Notion API wrapper includes comprehensive error handling:

### Built-in Retry Logic

```python
# Automatic retry with exponential backoff
def _retry_with_exponential_backoff(self, func, *args, **kwargs):
    # Retries up to max_retries times
    # Uses exponential backoff: 1s, 2s, 4s, 8s, etc.
    # Handles rate limiting automatically
```

### Common Exceptions

```python
from notion_client import APIError, RequestTimeoutError

try:
    result = notion.query_database()
except APIError as e:
    if e.code == "unauthorized":
        print("Invalid token or insufficient permissions")
    elif e.code == "object_not_found":
        print("Database not found or not shared with integration")
    else:
        print(f"API Error: {e.message}")
except RequestTimeoutError:
    print("Request timed out - check network connection")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Advanced Usage

### Custom Property Handling

```python
# Working with different property types
def extract_property_value(page, property_name):
    prop = page['properties'].get(property_name)
    if not prop:
        return None

    prop_type = prop['type']

    if prop_type == 'title':
        return prop['title'][0]['plain_text'] if prop['title'] else ""
    elif prop_type == 'rich_text':
        return prop['rich_text'][0]['plain_text'] if prop['rich_text'] else ""
    elif prop_type == 'select':
        return prop['select']['name'] if prop['select'] else None
    elif prop_type == 'multi_select':
        return [item['name'] for item in prop['multi_select']]
    elif prop_type == 'date':
        return prop['date']['start'] if prop['date'] else None
    elif prop_type == 'number':
        return prop['number']
    elif prop_type == 'checkbox':
        return prop['checkbox']
    else:
        return str(prop)

# Usage
pages = notion.query_database()
for page in pages['results']:
    title = extract_property_value(page, 'Name')
    status = extract_property_value(page, 'Status')
    priority = extract_property_value(page, 'Priority')
    print(f"{title}: {status} (Priority: {priority})")
```

### Async Operations

For high-performance operations, the wrapper includes async methods:

```python
import asyncio

async def process_pages_async():
    # The wrapper handles async operations internally
    # for content updates and bulk operations

    # Large content updates are processed asynchronously
    await notion.update_page_content(
        page_id=page_id,
        content=large_content,
        status="Processing"
    )
```

### Performance Optimization

```python
# Batch operations for better performance
page_ids = [page['id'] for page in pages['results']]

# Update statuses in batch (more efficient than individual updates)
notion.update_tickets_status_batch(page_ids, "Processing")

# Use pagination for large datasets
def get_all_pages():
    all_pages = []
    start_cursor = None

    while True:
        result = notion.query_database(
            start_cursor=start_cursor,
            page_size=100  # Maximum allowed
        )

        all_pages.extend(result['results'])

        if not result.get('has_more'):
            break

        start_cursor = result['next_cursor']

    return all_pages
```

## Configuration Examples

### Environment Variables

```env
# Required
NOTION_TOKEN=secret_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
NOTION_BOARD_DB=d4f2a1b8c5e74321987654321fedcba0

# Optional - for advanced configuration
NOTION_API_VERSION=2022-06-28
NOTION_REQUEST_TIMEOUT=30
NOTION_MAX_RETRIES=5
```

### Programmatic Configuration

```python
from nomad.utils.global_config import get_global_config

# Configure through global config
config = get_global_config()
notion = NotionClientWrapper(
    token=config.get("NOTION_TOKEN"),
    database_id=config.get("NOTION_BOARD_DB"),
    max_retries=int(config.get("NOTION_MAX_RETRIES", "3"))
)
```

## Debugging

### Enable Debug Logging

```python
import logging

# Enable debug logging for Notion operations
logging.getLogger('nomad.clients.notion_wrapper').setLevel(logging.DEBUG)

# Run operations - detailed logs will be shown
notion.test_connection()
```

### Schema Inspection

```python
# Inspect database schema
schema = notion.debug_database_schema()

print("Database Properties:")
for prop_name, prop_config in schema['properties'].items():
    print(f"  {prop_name}: {prop_config['type']}")
    if prop_config['type'] == 'select':
        options = [opt['name'] for opt in prop_config['select']['options']]
        print(f"    Options: {options}")
```

## Best Practices

1. **Connection Testing**: Always test connection before operations
2. **Error Handling**: Implement proper exception handling
3. **Rate Limiting**: Respect API rate limits (built into wrapper)
4. **Batch Operations**: Use batch methods for multiple updates
5. **Property Validation**: Validate property types before updates
6. **Content Size**: Be mindful of content size limits
7. **Pagination**: Handle pagination for large datasets

## Troubleshooting

### Common Issues

#### "unauthorized" Error
- Check if `NOTION_TOKEN` is correct
- Verify integration has access to the workspace
- Ensure database is shared with the integration

#### "object_not_found" Error
- Verify `NOTION_BOARD_DB` is correct
- Check if database exists and is accessible
- Ensure integration has permission to access the database

#### Rate Limiting
- The wrapper handles rate limiting automatically
- If you see persistent rate limit errors, reduce concurrent operations

#### Content Update Failures
- Large content may time out - wrapper handles this with chunking
- Check for invalid markdown or special characters
- Verify page exists and is editable

---

*Notion API documentation for Nomad v0.2.0. For more examples, see the [examples directory](../examples/notion-integration/).*
