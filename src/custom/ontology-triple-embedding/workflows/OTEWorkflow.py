from enum import Enum
from fastapi import APIRouter
from abi.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from abi.services.cache.CacheFactory import CacheFactory
import requests
import os
import rdflib
from dataclasses import dataclass
from langchain_core.tools import BaseTool

# We initialize a cache for the workflow.
cache = CacheFactory.CacheFS_find_storage(subpath="ontology-triple-embedding")

@dataclass
class OTEWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for OTEWorkflow."""
    ontology: str # Can be a path to a file or an http url
    ontology_format: str = "xml"

class OTEWorkflowParameters(WorkflowParameters):
    """Parameters for OTEWorkflow."""
    pass


class OTEWorkflow(Workflow[OTEWorkflowParameters]):
    """Workflow for OTE."""
    _graph: rdflib.Graph

    def __init__(self, configuration: OTEWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self._load_ontology()
        self._compute_embeddings()
        
    def _load_ontology(self):
        ontology : str | None = None

        ontology_graph_cache_key = f'{self.__configuration.ontology}_{self.__configuration.ontology_format}_graph'
        # If the rdflib graph is cached we load it.        
        if cache.exists(ontology_graph_cache_key):
            self._graph = cache.get(ontology_graph_cache_key)
            return 

        
        if self.__configuration.ontology.startswith("http"):
            # This is made to download once and only once.
            if cache.exists(self.__configuration.ontology):
                ontology = cache.get(self.__configuration.ontology)
            else:
                response = requests.get(self.__configuration.ontology)
                ontology = response.text
                cache.set_text(self.__configuration.ontology, ontology)    
        else:
            # If it's a local file it will be read every time.
            with open(os.path.dirname(__file__) + "/ontologies/" + self.__configuration.ontology, "r") as file:
                ontology = file.read()
        
        # At that point we should have the ontology as a string.
        assert ontology is not None, "Failed to load ontology"

        graph = rdflib.Graph()
        graph.parse(data=ontology, format=self.__configuration.ontology_format)
        
        # This is storing the graph in the cache so the next time it's called it will be loaded from the cache directly. (see the first if statement of this method)
        cache.set_pickle(ontology_graph_cache_key, graph)

        self._graph = graph
    
    def _compute_embeddings(self):
        # We create a map of subjects.
        subjects_map = {}
        for s, p, o in self._graph.triples((None, None, None)):
            if s not in subjects_map:
                subjects_map[s] = []
            subjects_map[s].append((p, o))
        
        subject_chunks = {}
        
        for subject in subjects_map:
            labels = list(filter(lambda x: x[0] == rdflib.RDFS.label, subjects_map[subject]))
            definitions = list(filter(lambda x: x[0] == rdflib.SKOS.definition, subjects_map[subject]))
            comments = list(filter(lambda x: x[0] == rdflib.RDFS.comment, subjects_map[subject]))
            examples = list(filter(lambda x: x[0] == rdflib.SKOS.example, subjects_map[subject]))
            notes = list(filter(lambda x: x[0] == rdflib.SKOS.note, subjects_map[subject]))
            
            term_chunks = []
            if len(labels) > 0:
                term_chunks.append('Labels:\n' + '\n'.join([v[1] for v in labels]))
            if len(definitions) > 0:
                term_chunks.append('Definitions:\n' + '\n'.join([v[1] for v in definitions]))
            if len(comments) > 0:
                term_chunks.append('Comments:\n' + '\n'.join([v[1] for v in comments]))
            if len(examples) > 0:
                term_chunks.append('Examples:\n' + '\n'.join([v[1] for v in examples]))
            if len(notes) > 0:
                term_chunks.append('Notes:\n' + '\n'.join([v[1] for v in notes]))
            
            term_chunk = '\n'.join(term_chunks)
            
            subject_chunks[subject] = term_chunk
            
        #To be continued...
        
        

            
    

    
    def as_api(self, router: APIRouter, route_name: str = "", name: str = "", description: str = "", description_stream: str = "", tags: list[str | Enum] | None = ...) -> None:
        return super().as_api(router, route_name, name, description, description_stream, tags)
    
    def as_tools(self) -> list[BaseTool]:
        return []
        
if __name__ == "__main__":
    import click
    
    @click.command()
    @click.option(
        '--ontology',
        '-o',
        required=True,
        help='Path to ontology file or HTTP URL to download the ontology from'
    )
    @click.option(
        '--format',
        '-f',
        'ontology_format',
        default='owl',
        help='Format of the ontology file (e.g., owl, turtle, xml, n3)',
        show_default=True
    )
    def main(ontology: str, ontology_format: str):
        """
        OTE (Ontology Triple Embedding) Workflow CLI
        
        Load and process an ontology file for triple embedding.
        """
        click.echo(f"Loading ontology: {ontology}")
        click.echo(f"Format: {ontology_format}")
        
        try:
            # Create workflow configuration
            config = OTEWorkflowConfiguration(
                ontology=ontology,
                ontology_format=ontology_format
            )
            
            # Initialize workflow
            workflow = OTEWorkflow(configuration=config)
            
            # Display success information
            click.secho("✓ Ontology loaded successfully!", fg='green', bold=True)
            click.echo(f"Graph contains {len(workflow._graph)} triples")
            
            # Display some basic statistics
            click.echo("\nGraph Statistics:")
            click.echo(f"  - Total triples: {len(workflow._graph)}")
            
        except Exception as e:
            click.secho(f"✗ Error: {str(e)}", fg='red', bold=True)
            raise click.Abort()
    
    main()
