# Authentication API

The Authentication API provides endpoints and interfaces for managing authentication and authorization within the ABI framework. This includes user management, API key generation, token issuance, and permission control.

## REST API

### Authentication Endpoints

#### Login

Authenticates a user and returns an access token.

```
POST /api/v1/auth/login
```

**Request Body:**

```json
{
  "username": "user@example.com",
  "password": "securepassword"
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

#### Refresh Token

Refreshes an expired access token using a refresh token.

```
POST /api/v1/auth/refresh
```

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

#### Logout

Invalidates the current session.

```
POST /api/v1/auth/logout
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "message": "Successfully logged out"
  }
}
```

### API Key Management

#### Generate API Key

Creates a new API key for the authenticated user.

```
POST /api/v1/auth/api-keys
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Production API Key",
  "expires_at": "2024-12-31T23:59:59Z",
  "scopes": ["read:assistants", "write:assistants", "read:workflows"]
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "apk_123456789",
    "name": "Production API Key",
    "key": "sk_live_abcdefghijklmnopqrstuvwxyz",
    "created_at": "2023-05-01T12:00:00Z",
    "expires_at": "2024-12-31T23:59:59Z",
    "scopes": ["read:assistants", "write:assistants", "read:workflows"],
    "last_used_at": null
  },
  "message": "API key created successfully. Store this key securely as it will not be shown again."
}
```

#### List API Keys

Returns all API keys belonging to the authenticated user.

```
GET /api/v1/auth/api-keys
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "apk_123456789",
        "name": "Production API Key",
        "created_at": "2023-05-01T12:00:00Z",
        "expires_at": "2024-12-31T23:59:59Z",
        "scopes": ["read:assistants", "write:assistants", "read:workflows"],
        "last_used_at": "2023-05-01T14:30:00Z"
      },
      {
        "id": "apk_987654321",
        "name": "Development API Key",
        "created_at": "2023-04-15T10:00:00Z",
        "expires_at": "2024-04-15T10:00:00Z",
        "scopes": ["read:assistants", "read:workflows"],
        "last_used_at": "2023-04-30T09:15:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_items": 2,
      "total_pages": 1
    }
  }
}
```

#### Revoke API Key

Invalidates an API key.

```
DELETE /api/v1/auth/api-keys/{api_key_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "message": "API key revoked successfully"
  }
}
```

### User Management

#### Create User

Creates a new user account (admin only).

```
POST /api/v1/auth/users
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "email": "newuser@example.com",
  "password": "securepassword",
  "first_name": "John",
  "last_name": "Doe",
  "role": "developer"
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "usr_123456789",
    "email": "newuser@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "developer",
    "created_at": "2023-05-01T12:00:00Z",
    "last_login_at": null
  }
}
```

#### Get Current User

Returns information about the currently authenticated user.

```
GET /api/v1/auth/me
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "usr_123456789",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "admin",
    "created_at": "2022-01-01T00:00:00Z",
    "last_login_at": "2023-05-01T12:00:00Z",
    "permissions": [
      "assistants:read",
      "assistants:write",
      "workflows:read",
      "workflows:write",
      "pipelines:read",
      "pipelines:write",
      "users:read",
      "users:write"
    ]
  }
}
```

#### Update Password

Updates the password for the authenticated user.

```
PUT /api/v1/auth/password
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "current_password": "currentSecurePassword",
  "new_password": "newSecurePassword"
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "message": "Password updated successfully"
  }
}
```

## Python API

### Authentication

```python
from abi.auth import AuthClient

# Initialize client
auth_client = AuthClient()

# Login with username and password
login_result = auth_client.login(
    username="user@example.com",
    password="securepassword"
)

# Get the access token
access_token = login_result.access_token

# Create client with token
auth_client = AuthClient(access_token=access_token)

# Refresh an expired token
refresh_result = auth_client.refresh_token(
    refresh_token=login_result.refresh_token
)

# Logout
auth_client.logout()
```

### API Key Management

```python
from abi.auth import ApiKeyManager

# Initialize with access token
api_key_manager = ApiKeyManager(access_token=access_token)

# Generate a new API key
api_key = api_key_manager.create_key(
    name="Production API Key",
    expires_at="2024-12-31T23:59:59Z",
    scopes=["read:assistants", "write:assistants", "read:workflows"]
)

# Store this securely
print(f"API Key: {api_key.key}")

# List all API keys
api_keys = api_key_manager.list_keys()
for key in api_keys:
    print(f"{key.name} - {key.id} - Expires: {key.expires_at}")

# Revoke an API key
api_key_manager.revoke_key(key_id="apk_123456789")
```

### User Management

```python
from abi.auth import UserManager

# Initialize with access token (requires admin privileges)
user_manager = UserManager(access_token=access_token)

# Create a new user
new_user = user_manager.create_user(
    email="newuser@example.com",
    password="securepassword",
    first_name="John",
    last_name="Doe",
    role="developer"
)

# Get the current user
current_user = user_manager.get_current_user()
print(f"Logged in as: {current_user.email}")

# Update password
user_manager.update_password(
    current_password="currentSecurePassword",
    new_password="newSecurePassword"
)
```

## Role-Based Access Control

ABI implements a role-based access control system with predefined roles:

| Role | Description |
|------|-------------|
| admin | Full system access |
| developer | Can create and manage assistants, workflows, and pipelines |
| analyst | Can view and execute workflows and query data |
| user | Basic access to use assistants and view workflows |

Each role has a set of permissions that determine what actions they can perform:

| Permission | Description |
|------------|-------------|
| assistants:read | View assistants |
| assistants:write | Create and modify assistants |
| workflows:read | View workflows |
| workflows:write | Create and modify workflows |
| workflows:execute | Execute workflows |
| pipelines:read | View pipelines |
| pipelines:write | Create and modify pipelines |
| integrations:read | View integrations |
| integrations:write | Create and modify integrations |
| users:read | View user accounts |
| users:write | Create and modify user accounts |

## Custom Scopes

When creating API keys, you can specify custom scopes to limit access:

```python
api_key = api_key_manager.create_key(
    name="Limited API Key",
    scopes=["read:assistants", "read:workflows", "execute:workflows:sales-analysis"]
)
```

This creates an API key that can:
- Read all assistants
- Read all workflows
- Execute only the "sales-analysis" workflow

## Best Practices

1. **API Key Security**: 
   - Store API keys securely
   - Never expose keys in client-side code
   - Use scoped keys with minimal permissions
   - Rotate keys periodically

2. **Token Management**:
   - Store refresh tokens securely
   - Implement token refresh logic in your client
   - Handle token expiration gracefully

3. **Password Security**:
   - Use strong, unique passwords
   - Implement password rotation policies
   - Consider multi-factor authentication for admin accounts

4. **Monitoring and Alerting**:
   - Monitor for unusual authentication patterns
   - Set up alerts for multiple failed login attempts
   - Review API key usage regularly

## Error Handling

Common authentication errors:

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 401 | INVALID_CREDENTIALS | Incorrect username or password |
| 401 | EXPIRED_TOKEN | The access token has expired |
| 401 | INVALID_TOKEN | The token is invalid or malformed |
| 401 | REVOKED_TOKEN | The token has been revoked |
| 403 | INSUFFICIENT_PERMISSIONS | The user lacks required permissions |
| 403 | SCOPE_REQUIRED | The API key lacks required scope |

Example error response:

```json
{
  "status": "error",
  "data": null,
  "message": "Authentication failed",
  "errors": [
    {
      "code": "EXPIRED_TOKEN",
      "detail": "The access token has expired"
    }
  ]
}
```

## Next Steps

- Learn about [System API](system.md) for managing system-wide settings
- Explore the [Assistants API](assistants.md) to create AI assistants
- Check the [Workflows API](workflows.md) to build business processes 