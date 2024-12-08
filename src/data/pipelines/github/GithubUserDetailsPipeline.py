from dataclasses import dataclass
from abi.pipeline import Pipeline, PipelineConfiguration
from rdflib import Graph, RDF, OWL, URIRef, Namespace, Literal, XSD
from src.integrations.GithubIntegration import GithubIntegration

@dataclass
class GithubUserDetailsPipelineConfiguration(PipelineConfiguration):
    """Configuration for Github user details pipeline.
    
    Attributes:
        github_username (str): Username of the Github user to fetch details for
    """
    github_username: str

class GithubUserDetailsPipeline(Pipeline):
    __github_integration: GithubIntegration
    __configuration: GithubUserDetailsPipelineConfiguration
    
    def __init__(self, github_integration: GithubIntegration, configuration: GithubUserDetailsPipelineConfiguration):
        super().__init__([github_integration], configuration)
        
        self.__github_integration = github_integration
        self.__configuration = configuration
        

    def run(self) -> Graph:
        user_details = self.__github_integration.get_user_details(self.__configuration.github_username)
        
        graph = Graph()
        
        # Create base URI for GitHub user
        user_uri = URIRef(user_details["html_url"])
        
        # Define GitHub ontology namespace (you might want to move this to a constants file)
        GH = Namespace("http://github.com/ontology#")
        FOAF = Namespace("http://xmlns.com/foaf/0.1/")
        
        # Add namespace bindings
        graph.bind("gh", GH)
        graph.bind("foaf", FOAF)
        
        # Basic type assertions
        graph.add((user_uri, RDF.type, OWL.NamedIndividual))
        graph.add((user_uri, RDF.type, FOAF.Person))
        
        # Add user properties
        if user_details["name"]:
            graph.add((user_uri, FOAF.name, Literal(user_details["name"])))
        
        if user_details["email"]:
            graph.add((user_uri, FOAF.mbox, Literal(user_details["email"])))
        
        if user_details["location"]:
            graph.add((user_uri, FOAF.based_near, Literal(user_details["location"])))
        
        # GitHub specific properties
        graph.add((user_uri, GH.login, Literal(user_details["login"])))
        graph.add((user_uri, GH.followers_count, Literal(user_details["followers"])))
        graph.add((user_uri, GH.following_count, Literal(user_details["following"])))
        graph.add((user_uri, GH.public_repos_count, Literal(user_details["public_repos"])))
        graph.add((user_uri, GH.created_at, Literal(user_details["created_at"], datatype=XSD.dateTime)))
        
        if user_details["bio"]:
            graph.add((user_uri, GH.bio, Literal(user_details["bio"])))
        
        if user_details["company"]:
            graph.add((user_uri, GH.company, Literal(user_details["company"])))
        
        return graph