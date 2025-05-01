from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService, OntologyEvent
from dataclasses import dataclass
from pydantic import Field
from typing import Optional, Any
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from abi import logger
from src.core.modules.ontology.pipelines.AddCommercialOrganizationPipeline import AddCommercialOrganizationPipeline, AddCommercialOrganizationPipelineConfiguration, AddCommercialOrganizationPipelineParameters
from src.core.modules.ontology.pipelines.AddWebsitePipeline import AddWebsitePipeline, AddWebsitePipelineConfiguration, AddWebsitePipelineParameters
from src.core.modules.ontology.pipelines.AddFacilityOfficePipeline import AddFacilityOfficePipeline, AddFacilityOfficePipelineConfiguration, AddFacilityOfficePipelineParameters
from src.custom.modules.linkedin.integrations.LinkedInIntegration import LinkedInIntegration, LinkedInIntegrationConfiguration
from src.custom.modules.linkedin.pipelines.AddLinkedInIndustryPipeline import AddLinkedInIndustryPipeline, AddLinkedInIndustryPipelineConfiguration, AddLinkedInIndustryPipelineParameters
from src.custom.modules.linkedin.pipelines.AddLinkedInCompanyPagePipeline import AddLinkedInCompanyPagePipeline, AddLinkedInCompanyPagePipelineConfiguration, AddLinkedInCompanyPagePipelineParameters
from rdflib import URIRef, Literal, RDFS, Namespace
from pydash import find
import pydash as _
from urllib.parse import quote

URI_REGEX = r"http:\/\/ontology\.naas\.ai\/abi\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class LinkedInOrganizationInfoPipelineConfiguration(PipelineConfiguration):
    """Configuration for LinkedIn Organization Pipeline.
    
    Attributes:
        linkedin_integration_config (LinkedInIntegrationConfiguration): LinkedIn integration configuration
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    linkedin_integration_config: LinkedInIntegrationConfiguration
    add_commercial_organization_pipeline_configuration: AddCommercialOrganizationPipelineConfiguration
    add_website_pipeline_configuration: AddWebsitePipelineConfiguration
    add_linkedin_industry_pipeline_configuration: AddLinkedInIndustryPipelineConfiguration
    add_linkedin_company_page_pipeline_configuration: AddLinkedInCompanyPagePipelineConfiguration
    add_facility_office_pipeline_configuration: AddFacilityOfficePipelineConfiguration

class LinkedInOrganizationInfoPipelineParameters(PipelineParameters):
    """Parameters for LinkedIn Organization Pipeline execution.
    
    Attributes:
        linkedin_url (str): LinkedIn profile or organization post URL
        use_cache (bool): Use cache to store the data
    """
    organization_uri: Optional[str] = Field(None, description="URI of the organization to update with the information found on LinkedIn.", pattern=URI_REGEX)

class LinkedInOrganizationInfoPipeline(Pipeline):
    """Pipeline for fetching LinkedIn organization information."""
    __configuration: LinkedInOrganizationInfoPipelineConfiguration
    
    def __init__(self, configuration: LinkedInOrganizationInfoPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__linkedin_integration = LinkedInIntegration(self.__configuration.linkedin_integration_config)
        self.__add_commercial_organization_pipeline = AddCommercialOrganizationPipeline(self.__configuration.add_commercial_organization_pipeline_configuration)
        self.__add_website_pipeline = AddWebsitePipeline(self.__configuration.add_website_pipeline_configuration)
        self.__add_linkedin_industry_pipeline = AddLinkedInIndustryPipeline(self.__configuration.add_linkedin_industry_pipeline_configuration)
        self.__add_linkedin_company_page_pipeline = AddLinkedInCompanyPagePipeline(self.__configuration.add_linkedin_company_page_pipeline_configuration)
        self.__add_facility_office_pipeline = AddFacilityOfficePipeline(self.__configuration.add_facility_office_pipeline_configuration)

    def get_picture_urls(self, data, key):
        """
        Extracts picture URLs from a nested dictionary.

        Args:
            data (dict): The dictionary containing picture data.
            key (str): The key to extract picture URLs from.

        Returns:
            list: A list of picture URLs.
        """
        urls = []
        root_url = _.get(data, f"{key}.image.rootUrl")
        if root_url:
            for artifact in _.get(data, f"{key}.image.artifacts", []):
                file_url = artifact.get("fileIdentifyingUrlPathSegment")
                profile_url = f"{root_url}{file_url}"
                urls.append(profile_url)
        return urls
    
    def get_linkedin_url(self, organization_uri: str) -> str:
        graph = self.__configuration.triple_store.get_subject_graph(organization_uri)
        predicate = URIRef("http://ontology.naas.ai/abi/hasLinkedInPage")
        objects = list(graph.objects(predicate=predicate))
        linkedin_public_id = None
        linkedin_url = None
        for object in objects:
            graph_object = self.__configuration.triple_store.get_subject_graph(object)
            for s, p, o in graph_object:
                if p == URIRef("http://ontology.naas.ai/abi/linkedin_public_id"):
                    linkedin_public_id = str(o)
                if p == URIRef("http://ontology.naas.ai/abi/linkedin_public_url"):
                    linkedin_url = str(o)
        return linkedin_public_id, linkedin_url, s
    
    def run(self, parameters: LinkedInOrganizationInfoPipelineParameters) -> dict:
        # Get LinkedIn page URL from organization URI
        linkedin_public_id, linkedin_url, linkedin_page_uri = self.get_linkedin_url(parameters.organization_uri)
        logger.info(f"Linkedin Public ID: {linkedin_public_id}")
        logger.info(f"Linkedin URL: {linkedin_url}")
        logger.info(f"Linkedin Page URI: {linkedin_page_uri}")
        linkedin_id_clean = quote(linkedin_public_id, safe='&')
        logger.info(f"Linkedin ID Clean: {linkedin_id_clean}")
        
        # Get organization info
        data = self.__linkedin_integration.get_organization_info(linkedin_url)
        if data is None:
            return f"No data found for LinkedIn URL: {linkedin_url}"
        
        # Get company data by filtering the included array
        company_data = find(
            data.get("included", []),
            lambda x: x.get("$type") == "com.linkedin.voyager.organization.Company" and x.get("url") == f"https://www.linkedin.com/company/{linkedin_id_clean}"
        )
        name = _.get(company_data, "name")
        website = _.get(company_data, "companyPageUrl")
        linkedin_public_id = _.get(company_data, "universalName")
        entity_urn = _.get(company_data, "entityUrn")
        linkedin_id = None
        linkedin_url = None
        if entity_urn:
            linkedin_id = entity_urn.split(":")[-1]
            linkedin_url = f"https://www.linkedin.com/company/{linkedin_id}"
        description = _.get(company_data, "description")

        country = None
        geographic_area = None
        city = None
        state = None
        postal_code = None
        address = None
        headquarter = _.get(company_data, "headquarter")
        if headquarter:
            country = _.get(headquarter, "country")
            geographic_area = _.get(headquarter, "geographicArea") 
            city = _.get(headquarter, "city")
            postal_code = _.get(headquarter, "postalCode")
            address = _.get(headquarter, "line1")
            state = _.get(headquarter, "state")
            logger.info(f"Country: {country}")
            logger.info(f"Geographic Area: {geographic_area}")
            logger.info(f"City: {city}")
            logger.info(f"State: {state}")
            logger.info(f"Postal Code: {postal_code}")
            logger.info(f"Address: {address}")

        logger.info(f"Name: {name}")
        logger.info(f"Website: {website}")
        logger.info(f"Linkedin ID: {linkedin_id}")
        logger.info(f"Linkedin URL: {linkedin_url}")
        logger.info(f"Description: {description}")


        logo_url = None
        image_urls = self.get_picture_urls(company_data, "logo")
        if len(image_urls) > 0:
            logo_url = image_urls[-1]
        logger.info(f"Logo URL: {logo_url}")

        # Get industry data by filtering the included array
        industries = _.get(company_data, "*companyIndustries", [])
        industry_data = [find(
            data.get("included", []),
            lambda x: x.get("$type") == "com.linkedin.voyager.common.Industry" and x.get("entityUrn") == industry
        ) for industry in industries]
        logger.info(f"Industries Data: {industry_data}")

        # Add linkedin page to triple store
        linkedin_company_page_uri = self.__add_linkedin_company_page_pipeline.run(AddLinkedInCompanyPagePipelineParameters(
            individual_uri=linkedin_page_uri,
            label=linkedin_url,
            page_name=name,
            description=description,
            entity_urn=entity_urn,
            linkedin_id=linkedin_id,
            linkedin_url=linkedin_url,
            linkedin_public_id=linkedin_public_id,
        ))
            
        # Add commercial organization to triple store
        organization_uri = self.__add_commercial_organization_pipeline.run(AddCommercialOrganizationPipelineParameters(
            individual_uri=parameters.organization_uri,
            label=name,
            logo_url=logo_url,
        ))

        # Add website to triple store
        if website:
            website_uri = self.__add_website_pipeline.run(AddWebsitePipelineParameters(
                label=website,
                owner_uris=[parameters.organization_uri],
            ))

        # Add LinkedIn industry to triple store
        if len(industry_data) > 0:
            for industry in industry_data:
                self.__add_linkedin_industry_pipeline.run(AddLinkedInIndustryPipelineParameters(
                    label=industry.get("localizedName"),
                    entity_urn=industry.get("entityUrn"),
                    organization_uri=parameters.organization_uri,
                ))

        # Add headquarter to triple store
        if headquarter and country:
            if country != "OO":
                query = f"""
                PREFIX abi: <http://ontology.naas.ai/abi/>
                SELECT ?country WHERE {{
                    ?country abi:country_code "{country}" .
                }}
                """
                results = self.__configuration.triple_store.query(query)
                for result in results:
                    country_uri = result['country']
                    logger.info(f"Country URI: {country_uri}")
                    break
                if country_uri:
                    self.__add_facility_office_pipeline.run(AddFacilityOfficePipelineParameters(
                        label=f"{name} - Headquarter",
                        class_uri=ABI.GlobalHeadquarters,
                        organization_uri=parameters.organization_uri,
                        address=address,
                        city=city,
                        state=state,
                        postal_code=postal_code,
                        geographic_area=geographic_area,
                        country_uri=country_uri,
                    ))
        return organization_uri

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="linkedin_get_organization_info",
                description="Extract organization information from LinkedIn using LinkedIn URL and add it to triple store.",
                func=lambda **kwargs: self.run(LinkedInOrganizationInfoPipelineParameters(**kwargs)),
                args_schema=LinkedInOrganizationInfoPipelineParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass