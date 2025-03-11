from dataclasses import dataclass
from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from src.core.modules.common.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from pydantic import Field
from abi.utils.Graph import ABIGraph, ABI
from rdflib import Graph
from datetime import datetime
from abi import logger

LOGO_URL = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"

@dataclass
class GithubUserDetailsPipelineConfiguration(PipelineConfiguration):
    """Configuration for Github user details pipeline.
    
    Attributes:
        github_integration_config (GithubIntegrationConfiguration): The GitHub REST API integration instance
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "github"
    """
    github_integration_config: GithubIntegrationConfiguration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "github"


class GithubUserDetailsPipelineParameters(PipelineParameters):
    """Parameters for GithubUserDetailsPipeline execution.
    
    Attributes:
        github_username (str): Username of the Github user to fetch details for
    """
    github_username: str = Field(..., description="GitHub username, ID or URL to fetch details for")


class GithubUserDetailsPipeline(Pipeline):
    """Pipeline for adding a GitHub user to the ontology."""
    __configuration: GithubUserDetailsPipelineConfiguration
    
    def __init__(self, configuration: GithubUserDetailsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)

    def run(self, parameters: GithubUserDetailsPipelineParameters) -> Graph:
        # Init graph
        graph = ABIGraph()
        if parameters.github_username.startswith("https://github.com/"):
            parameters.github_username = parameters.github_username.split("/")[-1].split("?")[0]
        
        # Get user details from GithubIntegration
        # Schema for user details response:
        # {
        #   "login": str,           # The user's GitHub username
        #   "id": int,              # The unique identifier for the user
        #   "node_id": str,         # The GraphQL node ID
        #   "avatar_url": str,      # URL to user's avatar image
        #   "gravatar_id": str,     # The user's gravatar ID if set
        #   "url": str,             # API URL for this user
        #   "html_url": str,        # Web URL for this user's profile
        #   "followers_url": str,   # API URL for user's followers
        #   "following_url": str,   # API URL for users this user follows
        #   "gists_url": str,       # API URL for user's gists
        #   "starred_url": str,     # API URL for user's starred repos
        #   "subscriptions_url": str, # API URL for user's subscriptions
        #   "organizations_url": str, # API URL for user's organizations
        #   "repos_url": str,       # API URL for user's repositories
        #   "events_url": str,      # API URL for user's events
        #   "received_events_url": str, # API URL for events received by user
        #   "type": str,            # The type of user account
        #   "site_admin": bool,     # Whether user is a GitHub admin
        #   "name": str,            # The user's full name
        #   "company": str,         # The user's company
        #   "blog": str,            # The user's blog URL
        #   "location": str,        # The user's location
        #   "email": str,           # The user's email address
        #   "hireable": bool,       # Whether user is available for hire
        #   "bio": str,             # The user's profile bio
        #   "twitter_username": str, # The user's Twitter username
        #   "public_repos": int,    # Number of public repositories
        #   "public_gists": int,    # Number of public gists
        #   "followers": int,       # Number of followers
        #   "following": int,       # Number of users being followed
        #   "created_at": str,      # ISO 8601 timestamp of account creation
        #   "updated_at": str       # ISO 8601 timestamp of last update
        # }
        data = self.__github_integration.get_user_details(parameters.github_username)
        logger.debug(f"Data: {data}")

        # Create GithubUser individual
        id = data.get("id")
        node_id = data.get("node_id")
        label = data.get("login")
        url = data.get("html_url")
        user_view_type = data.get("user_view_type")
        site_admin = data.get("site_admin", False)
        name = data.get("name")
        company = data.get("company")
        blog = data.get("blog")
        location = data.get("location")
        email = data.get("email")
        hireable = data.get("hireable")
        bio = data.get("bio")
        twitter_username = data.get("twitter_username")
        public_repos = data.get("public_repos", 0)
        public_gists = data.get("public_gists", 0)
        followers = data.get("followers", 0)
        following = data.get("following", 0)
        created_at = datetime.strptime(data.get("created_at"), "%Y-%m-%dT%H:%M:%SZ")
        updated_at = datetime.strptime(data.get("updated_at"), "%Y-%m-%dT%H:%M:%SZ")
        github_user = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=id,
            label=label,
            is_a=ABI.GitHubUser,
            node_id=node_id,
            url=url,
            bio=bio,
            public_repos=public_repos,
            public_gists=public_gists,
            followers=followers,
            following=following,
            created_date=created_at,
            updated_date=updated_at,
        )

        # Query ontology store to find existing person
        query = f"""
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX cco: <https://www.commoncoreontologies.org/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?person
        WHERE {{
            ?person a cco:ont00001262 .  # Person class
            OPTIONAL {{ ?person rdfs:label ?label }}
            OPTIONAL {{ ?person abi:hasEmailAddress/rdfs:label ?email }}
            FILTER(
                ?label = "{name}" ||
                ?email = "{email}" 
            )
        }}
        LIMIT 1
        """
        logger.debug(f"Query: {query}")
        results = self.__configuration.ontology_store.query(query)
        logger.debug(f"Results: {results}")

        if len(results) > 0:
            # Use existing person
            person = results[0]['person']
        else:
            # Create new person
            person = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=name,
                label=name,
                is_a=ABI.Person,
            )

        # Link GitHub user to person
        graph.add((github_user, ABI.isPlatformUserOf, person))
        graph.add((person, ABI.hasPlatformUser, github_user))

        # Create EmailAddress and relationship with User
        if email:
            email_address = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=email,
                label=email,
                is_a=ABI.EmailAddress,
            )

            # Create Relationship between GithubUser and NonNameIdentifier
            graph.add((github_user, ABI.usesEmail, email_address))
            graph.add((email_address, ABI.isEmailUsedBy, github_user))

            # Create Relationship between Person and NonNameIdentifier
            graph.add((person, ABI.hasEmailAddress, email_address))
            graph.add((email_address, ABI.isEmailAddressOf, person))

        # Create TwitterAccount as NonNameIdentifier (CCO Information Entity)
        if twitter_username:
            twitter_account = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=twitter_username,
                label=twitter_username,
                is_a=ABI.TwitterUser,
            )

            # Create Relationship between Person and TwitterAccount
            graph.add((person, ABI.isPlatformUserOf, twitter_account))
            graph.add((twitter_account, ABI.hasPlatformUser, person))

        # Insert to ontology store
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)
        return graph.serialize(format="turtle")
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[StructuredTool]: List containing the pipeline tool
        """
        return [StructuredTool(
            name="github_user_details",
            description="Fetches GitHub user details based on username",
            func=lambda **kwargs: self.run(GithubUserDetailsPipelineParameters(**kwargs)),
            args_schema=GithubUserDetailsPipelineParameters
        )]


    def as_api(
            self, 
            router: APIRouter, 
            route_name: str = "githubuserdetails", 
            name: str = "Github User Details to Ontology", 
            description: str = "Fetches a GitHub user's details and maps them to the ontology as a GitHub user.", 
            tags: list[str] = []
        ) -> None:
        @router.post(f"/{route_name}", name=name, description=description, tags=tags)
        def run(parameters: GithubUserDetailsPipelineParameters):
            return self.run(parameters).serialize(format="turtle")