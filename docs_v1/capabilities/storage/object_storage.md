## Object Storage Service

Object storage is agnostic of the data type.
Therefore it only works with bytes. Learn more about bytes in Python:
- [Python bytes() documentation](https://docs.python.org/3/library/stdtypes.html#bytes)
- [Real Python: Understanding Bytes in Python](https://realpython.com/python-strings/#bytes-objects)

### Get object in storage in JSON

```python
prefix = "datastore/your_module"
file_name = "your_file.json"
file_content = services.storage_service.get_object(
    prefix=prefix,
    key=file_name
).decode("utf-8")
data = json.loads(file_content)
```

### Put object in storage in JSON

```python
prefix = "datastore/your_module"
file_name = "your_file.json"
services.storage_service.put_object(
    prefix=prefix,
    key=file_name,
    content=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8")
)
```
### Delete object in storage

```python
prefix = "datastore/your_module"
file_name = "your_file.json"
services.storage_service.delete_object(prefix=prefix, key=file_name)
```
## Triple Store Service

The Triple Store Service utilizes the Object Storage Service as its backend storage mechanism for RDF triples.
This provides a scalable and persistent storage solution for the semantic data.

When implementing a pipeline that interacts with the Triple Store, the configuration must include an instance of ITripleStoreService as a dependency. 
This interface defines the contract for interacting with the triple store.

Here's an example of how to add and remove triples to the Triple Store:

```python
from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService

class YourPipelineConfiguration(PipelineConfiguration):
    triple_store: ITripleStoreService

class YourPipelineParameters(PipelineParameters):
    pass

class YourPipeline(Pipeline):
    def __init__(self, configuration: YourPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: YourPipelineParameters):
        graph_insert = Graph()
        graph_insert.add((URIRef("http://example.org/s"), URIRef("http://example.org/p"), Literal("o")))
        self.__configuration.triple_store.insert(graph_insert)

        graph_remove = Graph()
        graph_remove.add((URIRef("http://example.org/s"), URIRef("http://example.org/p"), Literal("o")))
        self.__configuration.triple_store.remove(graph_remove)
```