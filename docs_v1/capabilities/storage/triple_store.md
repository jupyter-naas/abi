# Triple Store Service

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