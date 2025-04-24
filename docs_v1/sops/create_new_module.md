# Create New Module

## Procedure

To create a new custom module, we will use the `create_module` command:

```bash
make create_module -e MODULE_NAME=your_module_name
```

This command will duplicate the `src/core/modules/example_module` directory to `src/custom/modules/your_module_name` and update the Makefile to be able to start chat with the agent created in the module.

You can then start developing all components of the module in the `src/custom/modules/your_module_name` directory.

## Test-Driven Development Approach
1. Start by writing tests in the appropriate `tests` folder
2. Run the test script to verify expected behavior
3. Implement the actual component code based on test requirements
4. Iterate and refine until tests pass



## Storage

Storage is managed through service abstractions that allow seamless switching between local and production environments. 
In production, we utilize AWS S3 for storage capabilities.
For local development, the system defaults to local file storage when ENV=dev is set in the .env configuration file.

### Object Storage Service

Object storage is agnostic of the data type.
Therefore it only works with bytes. Learn more about bytes in Python:
- [Python bytes() documentation](https://docs.python.org/3/library/stdtypes.html#bytes)
- [Real Python: Understanding Bytes in Python](https://realpython.com/python-strings/#bytes-objects)

Example of usage:

Get object in storage in JSON:

```python
prefix = "datastore/your_module"
file_name = "your_file.json"
file_content = services.storage_service.get_object(
    prefix=prefix,
    key=file_name
).decode("utf-8")
data = json.loads(file_content)
```

Put object in storage in JSON:

```python
prefix = "datastore/your_module"
file_name = "your_file.json"
services.storage_service.put_object(
    prefix=prefix,
    key=file_name,
    content=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8")
)
```
