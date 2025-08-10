# File System Tools

[Source Code](../../../lib/abi/services/agent/tools)

## Overview

The File System Tools provide ABI agents with secure, configurable access to file system operations. This capability enables agents to read, write, and manage files directly, making them more autonomous and useful for real-world tasks.

The tools are designed with security and flexibility in mind, featuring:
- **Configurable permissions** for different environments
- **Path validation** to prevent unauthorized access
- **File type restrictions** for security
- **Size limits** to prevent abuse
- **Comprehensive logging** for audit trails

## Architecture

### Core Components

1. **FileSystemTools**: Main class providing file operations
2. **FileSystemConfig**: Configuration management with security settings
3. **FileSystemPermissions**: Granular permission controls
4. **FileSystemConfigManager**: Global configuration registry

### Security Model

The file system tools implement a multi-layered security approach:

- **Path Validation**: All paths are validated against allowed/blocked directories
- **Permission Checks**: Operations are validated against configured permissions
- **File Type Restrictions**: Only allowed file extensions can be processed
- **Size Limits**: File sizes are limited to prevent abuse
- **Base Path Isolation**: All operations are restricted to configured base paths

## Usage

### Basic Integration

```python
from abi.services.agent.tools import FileSystemTools

# Initialize with default development configuration
file_tools = FileSystemTools(config_name="development")
tools = file_tools.as_tools()

# Add to agent
agent.tools.extend(tools)
```

### Configuration Options

#### Development Configuration
```python
# Full access for development
dev_tools = FileSystemTools(config_name="development")
# - Read/Write/Delete operations allowed
# - 50MB file size limit
# - All common file types allowed
# - Base path: current directory
```

#### Production Configuration
```python
# Restricted access for production
prod_tools = FileSystemTools(config_name="production")
# - Read/Write operations only (no delete)
# - 5MB file size limit
# - Limited file types (.txt, .md, .json, etc.)
# - Base path: storage directory
```

#### Restricted Configuration
```python
# Read-only access
restricted_tools = FileSystemTools(config_name="restricted")
# - Read operations only
# - 1MB file size limit
# - Very limited file types
# - Base path: storage/readonly
```

### Custom Configuration

```python
from abi.services.agent.tools import FileSystemConfig, FileSystemPermissions, config_manager

# Create custom configuration
custom_config = FileSystemConfig(
    base_path="custom_storage",
    permissions=FileSystemPermissions(
        can_read=True,
        can_write=True,
        can_delete=False,
        can_create_directories=True,
        can_move_files=False,
        can_copy_files=True,
        max_file_size=1024 * 1024,  # 1MB
        allowed_extensions={'.txt', '.md', '.json'}
    )
)

# Register configuration
config_manager.register_config("custom", custom_config)

# Use custom configuration
custom_tools = FileSystemTools(config_name="custom")
```

## Available Operations

### File Operations

#### Read File
```python
content = file_tools.read_file("path/to/file.txt")
```

#### Write File
```python
result = file_tools.write_file("path/to/file.txt", "content", overwrite=True)
```

#### Delete File
```python
result = file_tools.delete_file("path/to/file.txt", recursive=False)
```

#### Copy File
```python
result = file_tools.copy_file("source.txt", "destination.txt", overwrite=False)
```

#### Move File
```python
result = file_tools.move_file("source.txt", "destination.txt")
```

### Directory Operations

#### List Directory
```python
listing = file_tools.list_directory("path/to/directory", include_hidden=False, recursive=False)
```

#### Create Directory
```python
result = file_tools.create_directory("path/to/directory", parents=True)
```

### Information Operations

#### Get File Info
```python
info = file_tools.get_file_info("path/to/file.txt")
# Returns: name, path, size, type, permissions, timestamps, etc.
```

#### Search Files
```python
matches = file_tools.search_files("search/path", "*.txt", recursive=True)
```

## Configuration Reference

### FileSystemPermissions

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `can_read` | bool | True | Allow file reading |
| `can_write` | bool | True | Allow file writing |
| `can_delete` | bool | False | Allow file deletion |
| `can_create_directories` | bool | True | Allow directory creation |
| `can_move_files` | bool | False | Allow file moving |
| `can_copy_files` | bool | True | Allow file copying |
| `allowed_extensions` | Set[str] | Common types | Allowed file extensions |
| `max_file_size` | int | 10MB | Maximum file size in bytes |
| `max_directory_size` | int | 100MB | Maximum directory size in bytes |
| `allowed_paths` | Set[str] | Empty | Specific allowed paths |
| `blocked_paths` | Set[str] | System paths | Blocked system paths |
| `max_recursive_depth` | int | 5 | Maximum recursive depth |

### FileSystemConfig

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `base_path` | str | "." | Base path for operations |
| `permissions` | FileSystemPermissions | Default | Permission configuration |
| `enable_path_validation` | bool | True | Enable path validation |
| `enable_size_limits` | bool | True | Enable size limits |
| `enable_extension_validation` | bool | True | Enable extension validation |
| `enable_logging` | bool | True | Enable operation logging |
| `max_files_per_operation` | int | 1000 | Maximum files per operation |
| `timeout_seconds` | int | 30 | Operation timeout |
| `is_production` | bool | False | Production environment flag |
| `is_development` | bool | True | Development environment flag |

## Security Considerations

### Path Validation
- All paths are resolved relative to the base path
- System directories are blocked by default
- Custom allowed/blocked paths can be configured
- Path traversal attacks are prevented

### File Type Restrictions
- Only configured file extensions are allowed
- MIME type detection is available
- Binary files can be restricted
- Executable files are blocked by default

### Size Limits
- File size limits prevent abuse
- Directory size limits for recursive operations
- Content size validation before writing
- Configurable limits per environment

### Permission Model
- Granular permissions for each operation type
- Environment-specific defaults
- Runtime permission validation
- Audit logging for all operations

## Integration Examples

### Adding to Existing Agent

```python
from abi.services.agent.tools import FileSystemTools

def create_agent():
    # Initialize file system tools
    file_tools = FileSystemTools(config_name="development")
    
    # Create agent with tools
    agent = Agent(
        name="MyAgent",
        description="Agent with file system capabilities",
        chat_model=model,
        tools=file_tools.as_tools(),
        # ... other parameters
    )
    
    return agent
```

### Environment-Specific Configuration

```python
import os

def get_file_tools():
    # Use production config in production environment
    if os.getenv("ENVIRONMENT") == "production":
        return FileSystemTools(config_name="production")
    else:
        return FileSystemTools(config_name="development")
```

### Custom Workflow Integration

```python
def document_workflow():
    file_tools = FileSystemTools(config_name="development")
    
    # Create document structure
    file_tools.create_directory("documents/project")
    
    # Write project files
    file_tools.write_file("documents/project/README.md", "# Project Documentation")
    file_tools.write_file("documents/project/config.json", '{"version": "1.0.0"}')
    
    # List created files
    listing = file_tools.list_directory("documents/project")
    return listing
```

## Best Practices

### Security
1. **Use appropriate configurations** for each environment
2. **Validate file paths** before operations
3. **Set reasonable size limits** to prevent abuse
4. **Restrict file types** to only what's needed
5. **Monitor logs** for suspicious activity

### Performance
1. **Use appropriate base paths** to limit scope
2. **Set reasonable file limits** for operations
3. **Use recursive operations** carefully
4. **Monitor operation timeouts**

### Maintenance
1. **Regularly review configurations**
2. **Update blocked paths** as needed
3. **Monitor disk usage**
4. **Backup important data**

## Troubleshooting

### Common Issues

#### Permission Denied
```
ValueError: Read operation not permitted by current configuration
```
**Solution**: Check configuration permissions and ensure the operation is allowed.

#### Path Outside Base Path
```
ValueError: Path /etc/passwd is outside the allowed base path
```
**Solution**: Verify the path is within the configured base path and allowed directories.

#### File Size Exceeded
```
ValueError: File size 10485760 exceeds limit of 5242880
```
**Solution**: Increase the file size limit in configuration or reduce file size.

#### Extension Not Allowed
```
ValueError: File extension '.exe' not allowed by current configuration
```
**Solution**: Add the extension to allowed_extensions or use a different file type.

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('abi.services.agent.tools').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
- **Async operations** for better performance
- **File watching** for real-time updates
- **Compression support** for large files
- **Encryption integration** for sensitive data
- **Cloud storage adapters** for distributed access

### Extension Points
- **Custom validators** for specialized requirements
- **Plugin system** for additional operations
- **Webhook integration** for external notifications
- **Metrics collection** for usage analytics

## Conclusion

The File System Tools provide ABI agents with secure, flexible file system access while maintaining strict security controls. The configurable permission system allows for environment-specific restrictions, making it suitable for both development and production use.

By following the security best practices and using appropriate configurations, you can safely enable file system capabilities in your ABI agents while maintaining system integrity and preventing abuse.
