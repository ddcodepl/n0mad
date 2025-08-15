# API Method Name

## Overview
Brief description of what this API method does, its purpose, and when to use it.

## HTTP Request
```http
METHOD /api/v1/endpoint
```

## Authentication
Describe the authentication method required:
- Bearer token
- API key
- OAuth 2.0
- etc.

## Request Headers
| Header | Type | Required | Description |
|--------|------|----------|-------------|
| Authorization | string | Yes | Bearer token for authentication |
| Content-Type | string | Yes | Must be `application/json` |
| X-Custom-Header | string | No | Optional custom header |

## Parameters

### Path Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id | string | Yes | Unique identifier for the resource |

### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| limit | integer | No | 10 | Maximum number of results to return |
| offset | integer | No | 0 | Number of results to skip |
| filter | string | No | - | Filter criteria for results |

### Request Body
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Name of the resource |
| description | string | No | Optional description |
| config | object | No | Configuration object |

#### Request Body Example
```json
{
  "name": "Example Resource",
  "description": "This is an example resource",
  "config": {
    "setting1": "value1",
    "setting2": true,
    "setting3": 42
  }
}
```

## Request Examples

### cURL Example
```bash
curl -X POST "https://api.nomad.com/v1/endpoint" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Resource",
    "description": "This is an example resource"
  }'
```

### Python Example
```python
import requests

url = "https://api.nomad.com/v1/endpoint"
headers = {
    "Authorization": "Bearer YOUR_ACCESS_TOKEN",
    "Content-Type": "application/json"
}
data = {
    "name": "Example Resource",
    "description": "This is an example resource"
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

### JavaScript Example
```javascript
const response = await fetch('https://api.nomad.com/v1/endpoint', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_ACCESS_TOKEN',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'Example Resource',
    description: 'This is an example resource'
  })
});

const result = await response.json();
console.log(result);
```

## Response

### Success Response (200 OK)
```json
{
  "status": "success",
  "data": {
    "id": "12345",
    "name": "Example Resource",
    "description": "This is an example resource",
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  },
  "meta": {
    "timestamp": "2023-01-01T00:00:00Z",
    "request_id": "req_12345"
  }
}
```

### Response Fields
| Field | Type | Description |
|-------|------|-------------|
| status | string | Status of the request (success/error) |
| data | object | The response data |
| data.id | string | Unique identifier of the created resource |
| data.name | string | Name of the resource |
| data.description | string | Description of the resource |
| data.created_at | string | ISO 8601 timestamp of creation |
| data.updated_at | string | ISO 8601 timestamp of last update |
| meta | object | Metadata about the request |
| meta.timestamp | string | Server timestamp |
| meta.request_id | string | Unique request identifier |

## Error Responses

### 400 Bad Request
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request is invalid",
    "details": [
      {
        "field": "name",
        "message": "Name is required"
      }
    ]
  },
  "meta": {
    "timestamp": "2023-01-01T00:00:00Z",
    "request_id": "req_12345"
  }
}
```

### 401 Unauthorized
```json
{
  "status": "error",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or missing authentication token"
  }
}
```

### 403 Forbidden
```json
{
  "status": "error",
  "error": {
    "code": "FORBIDDEN",
    "message": "Insufficient permissions to access this resource"
  }
}
```

### 404 Not Found
```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "The requested resource was not found"
  }
}
```

### 429 Too Many Requests
```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after some time.",
    "retry_after": 60
  }
}
```

### 500 Internal Server Error
```json
{
  "status": "error",
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An internal server error occurred"
  }
}
```

## Status Codes
| Status Code | Description |
|-------------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid request parameters |
| 401 | Unauthorized - Invalid or missing authentication |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource already exists |
| 422 | Unprocessable Entity - Validation errors |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |

## Rate Limiting
This endpoint is subject to rate limiting:
- **Limit**: 100 requests per minute per API key
- **Headers**: Rate limit information is included in response headers:
  - `X-RateLimit-Limit`: Maximum requests per minute
  - `X-RateLimit-Remaining`: Remaining requests in current window
  - `X-RateLimit-Reset`: Timestamp when rate limit resets

## Webhooks
If this endpoint triggers webhooks, describe them here:
- **Event**: `resource.created`
- **Payload**: Same as success response
- **Delivery**: HTTP POST to configured webhook URL

## SDKs and Libraries
Links to official SDKs and community libraries:
- [Python SDK](link-to-python-sdk)
- [JavaScript SDK](link-to-js-sdk)
- [Go SDK](link-to-go-sdk)

## Related Endpoints
- [GET /api/v1/endpoint](get-endpoint.md) - Retrieve resources
- [PUT /api/v1/endpoint/{id}](put-endpoint.md) - Update a resource
- [DELETE /api/v1/endpoint/{id}](delete-endpoint.md) - Delete a resource

## Examples and Use Cases

### Use Case 1: Basic Resource Creation
Describe a common use case and provide a complete example.

### Use Case 2: Advanced Configuration
Describe a more advanced use case with complex parameters.

## Testing
Information about testing this endpoint:
- Test environment URL
- Test API keys
- Sample test data

---

**API Information**
- *Version*: v1
- *Last updated*: [Date]
- *Stability*: Stable/Beta/Alpha

**Need Help?**
- [API Support](mailto:api-support@nomad.com)
- [Developer Forum](https://forum.nomad.com)
- [GitHub Issues](https://github.com/nomad-notion-automation/nomad/issues)
