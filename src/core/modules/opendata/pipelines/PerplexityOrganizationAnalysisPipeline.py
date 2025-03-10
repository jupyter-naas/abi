from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass, field
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from abi import logger
from pydantic import Field
from typing import Dict, Optional, Any
from abi.utils.Graph import ABIGraph, ABI, BFO, CCO, XSD, TIME
from abi.utils.String import create_id_from_string
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src import config, secret
from src.core.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.core.workflows.abi.CreateOntologyYAML import CreateOntologyYAML, CreateOntologyYAMLConfiguration, CreateOntologyYAMLParameters
from ..workflows.PerplexityGetOrganizationWorkflows import PerplexityOrganizationWorkflows, PerplexityOrganizationWorkflowsConfiguration, PerplexityOrganizationParameters
import json
from src.core.mappings import COLORS_NODES

@dataclass
class PerplexityOrganizationAnalysisPipelineConfiguration(PipelineConfiguration):
    """Configuration for OrganizationAnalysis pipeline.
    
    Attributes:
        ontology_store (IOntologyStoreService): The ontology store service to use
        naas_integration_config (NaasIntegrationConfiguration): Configuration for Naas integration
        perplexity_organization_workflows_config (PerplexityOrganizationWorkflowsConfiguration): Configuration for PerplexityOrganizationWorkflows
        create_ontology_yaml_config (CreateOntologyYAMLConfiguration): Configuration for CreateOntologyYAML
    """
    ontology_store: IOntologyStoreService
    naas_integration_config: NaasIntegrationConfiguration
    perplexity_organization_workflows_config: PerplexityOrganizationWorkflowsConfiguration
    create_ontology_yaml_config: CreateOntologyYAMLConfiguration

class PerplexityOrganizationAnalysisPipelineParameters(PipelineParameters):
    """Parameters for PerplexityOrganizationAnalysisPipeline execution.
    
    Attributes:
        organization_name (str): Name of the organization to analyze
        website (str): Website of the organization
        use_cache (bool): Use cache to store the data
    """
    organization_name: str = Field(..., description="Name of the organization to analyze.")
    website: Optional[str] = Field(..., description="Website of the organization.")
    use_cache: Optional[bool] = Field(True, description="Use cache to store the data.")

class PerplexityOrganizationAnalysisPipeline(Pipeline):
    """Pipeline for analyzing organizations and mapping them to an ontology using Perplexity."""
    
    __configuration: PerplexityOrganizationAnalysisPipelineConfiguration
        
    def __init__(self, configuration: PerplexityOrganizationAnalysisPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(configuration.naas_integration_config)
        self.__perplexity_organization_workflows = PerplexityOrganizationWorkflows(configuration.perplexity_organization_workflows_config)
        self.__create_ontology_yaml = CreateOntologyYAML(configuration.create_ontology_yaml_config)
        
    def run(self, parameters: PerplexityOrganizationAnalysisPipelineParameters) -> None:
        # Initialize variables
        metadata = {}
        if parameters.website is not None:
            metadata = {
                "website": parameters.website
            }

        # Extract data from Perplexity
        logger.info(f"-----> Extracting data from Perplexity: {parameters.organization_name}, {parameters.website}")
        response = self.__perplexity_organization_workflows.get_organization_analysis(PerplexityOrganizationParameters(
            organization_name=parameters.organization_name,
            metadata=metadata,
            use_cache=parameters.use_cache
        ))
        organization_id = response["organization_id"]
        organization_storage_path = response["organization_storage_path"]

        # Load existing ontology
        logger.info(f"-----> Loading ontology: {organization_id}")
        graph = ABIGraph()
        try:    
            existing_graph = self.__configuration.ontology_store.get(organization_id)
            # Create new ABIGraph and merge existing data
            for triple in existing_graph:
                graph.add(triple)
        except Exception as e:
            logger.debug(f"Error getting graph: {e}")
            
        # Mapping - Add organization general information
        logger.info("---> Mapping organization general information to ontology")

        # Getting organization general information
        organization_general_information = response["organization_general_information"]
        organization_name = organization_general_information.get("name", None)
        organization_website = organization_general_information.get("website", None)
        organization_legal_name = organization_general_information.get("legal_name", None)    
        organization_type = organization_general_information.get("organization_type", None)
        organization_website = organization_general_information.get("website", None)
        organization_mission = organization_general_information.get("mission", None)
        organization_vision = organization_general_information.get("vision", None)
        organization_created_year = organization_general_information.get("created_year", None)
        organization_headquarters = organization_general_information.get("headquarters", [])
        organization_number_of_employee = organization_general_information.get("number_of_employees", None)
        organization_industries = organization_general_information.get("industries", [])
        organization_ticker_symbol = organization_general_information.get("ticker_symbol", None)
        organization_stock_market = organization_general_information.get("stock_market", None)

        # Cleaning organization details
        if isinstance(organization_headquarters, dict):
            organization_headquarters = [organization_headquarters]
        if isinstance(organization_industries, dict):
            organization_industries = [organization_industries]
        if organization_type == "commercial_organization":
            organization_class = CCO.ont00000443 # Commercial Organization
        elif organization_type == "civil_organization":
            organization_class = CCO.ont00001302 # Civil Organization
        elif organization_type == "educational_organization":
            organization_class = CCO.ont00000564 # Educational Organization
        elif organization_type == "government_organization":
            organization_class = CCO.ont00000408 # Government Organization
        else:
            raise ValueError(f"Organization type {organization_type} not supported")
        try:
            number_of_employee_value = int(organization_number_of_employee.get("value"))
        except:
            number_of_employee_value = None
        
        # Add organization to graph
        organization_uri = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=organization_id,
            label=organization_name,
            is_a=organization_class,
            mission=organization_mission,
            vision=organization_vision,
            website=organization_website,
            created_year=organization_created_year,
            number_of_employees=number_of_employee_value,
            ontology_group="General"
        )

        # Add legal name to graph
        organization_legal_name_uri = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=create_id_from_string(organization_legal_name),
            label=organization_legal_name,
            is_a=CCO.ont00001331,
            ontology_group="General",
        )
        graph.add((organization_uri, ABI.hasLegalName, organization_legal_name_uri))
        graph.add((organization_legal_name_uri, ABI.isLegalNameOf, organization_uri))

        # Add ticker to graph
        if organization_ticker_symbol is not None:
            ticker_uri = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=create_id_from_string(organization_ticker_symbol),
                label=organization_ticker_symbol,
                is_a=ABI.Ticker,
                ontology_group="General"
            )
            graph.add((organization_uri, ABI.hasTickerSymbol, ticker_uri))
            graph.add((ticker_uri, ABI.isTickerSymbolOf, organization_uri))

        # Add stock market to graph as a commercial organization
        if organization_stock_market is not None:
            stock_market_uri = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=create_id_from_string(organization_stock_market),
                label=organization_stock_market,
                is_a=CCO.ont00000443,
                ontology_group="Organization",
            )
            graph.add((stock_market_uri, CCO.ont00001977, organization_uri)) #has affiliate
            graph.add((organization_uri, CCO.ont00001939, stock_market_uri)) #is affiliated with

        # Add industries to graph
        if organization_industries is not None:
            for industry in organization_industries:
                industry_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=create_id_from_string(industry.get("name")),
                    label=industry.get("name"),
                    is_a=ABI.Industry,
                    definition=industry.get("definition"),
                    ontology_group="General"
                )
                graph.add((organization_uri, ABI.belongsToIndustry, industry_uri))
                graph.add((industry_uri, ABI.hasOrganization, organization_uri))

        # Add headquarters to graph
        if organization_headquarters is not None:
            for headquarter in organization_headquarters:
                if headquarter.get("type") == "global_headquarters":
                    class_headquarter = ABI.GlobalHeadquarters
                elif headquarter.get("type") == "regional_headquarters":
                    class_headquarter = ABI.RegionalHeadquarters
                headquarter_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=create_id_from_string(organization_name + "_headquarters"),
                    label=organization_name + " Headquarters",
                    is_a=class_headquarter,
                    ontology_group="General"
                )
                graph.add((organization_uri, ABI.hasFacility, headquarter_uri))
                graph.add((headquarter_uri, ABI.isFacilityOf, organization_uri))

                # Add country
                country_uri = None
                if headquarter.get("country") is not None:
                    country_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=create_id_from_string(headquarter.get("country")),
                        label=headquarter.get("country"),
                        is_a=ABI.Country,
                        ontology_group="General"
                    )
                    graph.add((headquarter_uri, BFO.BFO_0000171, country_uri)) #is located in
                    graph.add((country_uri, BFO.BFO_0000124, headquarter_uri)) #location of

                # Add state
                state_uri = None
                if headquarter.get("state") is not None:
                    state_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=create_id_from_string(headquarter.get("state")),
                        label=headquarter.get("state"),
                        is_a=ABI.State,
                        ontology_group="General"
                    )
                    graph.add((headquarter_uri, BFO.BFO_0000171, state_uri))
                    graph.add((state_uri, BFO.BFO_0000124, headquarter_uri))
                    graph.add((state_uri, BFO.BFO_0000171, country_uri))
                    graph.add((country_uri, BFO.BFO_0000124, state_uri))

                # Add city
                city_uri = None
                if headquarter.get("city") is not None:
                    city_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=create_id_from_string(headquarter.get("city")),
                        label=headquarter.get("city"),
                        is_a=CCO.ont00000887,
                        ontology_group="General"
                    )
                    graph.add((headquarter_uri, BFO.BFO_0000171, city_uri))
                    graph.add((city_uri, BFO.BFO_0000124, headquarter_uri))
                    if state_uri is not None:
                        graph.add((city_uri, BFO.BFO_0000171, state_uri))
                        graph.add((state_uri, BFO.BFO_0000124, city_uri))
                    if country_uri is not None:
                        graph.add((city_uri, BFO.BFO_0000171, country_uri))
                        graph.add((country_uri, BFO.BFO_0000124, city_uri))

                # Add address
                if headquarter.get("address") is not None:
                    address_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=create_id_from_string(organization_name + "_headquarters_address"),
                        label=headquarter.get("address"),
                        is_a=ABI.Address,
                        ontology_group="General"
                    )
                    graph.add((headquarter_uri, ABI.hasAddress, address_uri))
                    graph.add((address_uri, ABI.isAddressOf, headquarter_uri))

        # Maping organization members
        logger.info("---> Mapping organization members to ontology")
        organization_members = response["organization_members"]
        founders = organization_members.get("founders", [])
        chairmans = organization_members.get("chairmans", [])
        president = organization_members.get("president", {})
        vice_presidents = organization_members.get("vice_presidents", [])
        ceo = organization_members.get("ceo", {})
        cfo = organization_members.get("cfo", {})
        cto = organization_members.get("cto", {})

        # Add members to graph
        def add_member(graph, organization_uri, members, role_name):
            if members is None or not members:
                return graph
            if isinstance(members, dict):
                members = [members]

            # Add members
            for member in members:
                logger.info(f"-----> Member: {member}")
                if member.get("name") is None:
                    continue
                # Add Organization Member
                member_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=create_id_from_string(member.get("name")),
                    label=member.get("name"),
                    is_a=CCO.ont00000647,
                    ontology_group="Organization",
                    role=member.get("role"),
                    source=member.get("source"),
                    source_url=member.get("source_url"),
                    source_date=member.get("source_date")
                )
                # Add member to organization
                graph.add((organization_uri, CCO.ont00001977, member_uri))
                graph.add((member_uri, CCO.ont00001939, organization_uri))
                
                # Add Organization Member Role
                role_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=create_id_from_string(role_name),
                    label=role_name,
                    is_a=CCO.ont00000175,
                    ontology_group="Member"
                )
                graph.add((member_uri, ABI.hasRole, role_uri))
                graph.add((role_uri, ABI.isRoleOf, member_uri))
            return graph

        graph = add_member(graph, organization_uri, founders, "Founders")
        graph = add_member(graph, organization_uri, chairmans, "Board of Directors")
        graph = add_member(graph, organization_uri, president, "Top Management")
        graph = add_member(graph, organization_uri, vice_presidents, "Top Management")
        graph = add_member(graph, organization_uri, ceo, "Top Management")
        graph = add_member(graph, organization_uri, cfo, "Top Management")
        graph = add_member(graph, organization_uri, cto, "Top Management")

        # Add organization offerings
        logger.info(f"---> Mapping organization offerings")
        organization_offerings = response["organization_offerings"]
        organization_products = organization_offerings["products"]
        organization_services = organization_offerings["services"]
        organization_markets = organization_offerings["markets"]
        organization_market_segments = organization_offerings["market_segments"]
        organization_positionings = organization_offerings["positionings"]

        # Add offerings to graph
        def add_offering(graph, organization_uri, offerings, offering_class):
            if offerings is None or not offerings:
                return graph
            if isinstance(offerings, dict):
                offerings = [offerings]

            for offering in offerings:
                if offering.get("name") is None:
                    continue
                offering_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=create_id_from_string(offering["name"]),
                    label=offering["name"],
                    is_a=offering_class,
                    description=offering["description"],
                    ontology_group="Offering"
                )
                graph.add((organization_uri, ABI.hasOffering, offering_uri))
                graph.add((offering_uri, ABI.isOfferingOf, organization_uri))
            return graph

        graph = add_offering(graph, organization_uri, organization_products, ABI.Product)
        graph = add_offering(graph, organization_uri, organization_services, ABI.Service)

        # Add markets and market segments to graph
        def map_offerings(graph, object_uri, values, object_class, object_property, object_property_inverse):
            if values is None or not values:
                return graph
            if isinstance(values, dict):
                values = [values]

            for value in values:  
                value_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=create_id_from_string(value),
                    label=value,
                    is_a=object_class,
                    ontology_group="Offering"
                )
                graph.add((object_uri, object_property, value_uri))
                graph.add((value_uri, object_property_inverse, object_uri))
            return graph

        for market in organization_markets:
            market_uri = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=create_id_from_string(market["name"]),
                label=market["name"],
                is_a=ABI.Market,
                definition=market["definition"],
                ontology_group="Offering"
            )
            graph.add((organization_uri, ABI.hasMarket, market_uri))
            graph.add((market_uri, ABI.isMarketOf, organization_uri))
            organization_products = market.get("products", [])
            organization_services = market.get("services", [])
            graph = map_offerings(graph, market_uri, organization_products, ABI.Product, ABI.Targets, ABI.isTargetedBy)
            graph = map_offerings(graph, market_uri, organization_services, ABI.Service, ABI.Targets, ABI.isTargetedBy)

        for market_segment in organization_market_segments:
            if market_segment.get("name") is None:
                continue
            market_segment_uri = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=create_id_from_string(market_segment["name"]),
                label=market_segment["name"],
                is_a=ABI.MarketSegment,
                definition=market_segment["definition"],
                ontology_group="Offering"
            )
            market_uri = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=create_id_from_string(market_segment["market"]),
                label=market_segment["market"],
                is_a=ABI.Market,
                ontology_group="Offering"
            )
            graph.add((market_uri, ABI.hasMarketSegment, market_segment_uri))
            graph.add((market_segment_uri, ABI.isMarketSegmentOf, market_uri))
            market_segment_products = market_segment.get("products", [])
            market_segment_services = market_segment.get("services", [])
            graph = map_offerings(graph, market_segment_uri, market_segment_products, ABI.Product, ABI.Targets, ABI.isTargetedBy)
            graph = map_offerings(graph, market_segment_uri, market_segment_services, ABI.Service, ABI.Targets, ABI.isTargetedBy)

        # Add positionings to graph
        if organization_positionings is not None:
            for positioning in organization_positionings:
                if positioning.get("name") is None:
                    continue
                positioning_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=create_id_from_string(positioning["name"]),
                    label=positioning["name"],
                    is_a=ABI.Positioning,
                    definition=positioning["definition"],
                    ontology_group="Offering"
                )
                graph.add((organization_uri, ABI.hasPositioning, positioning_uri))
                graph.add((positioning_uri, ABI.isPositioningOf, organization_uri))
                organization_products = positioning.get("products", [])
                organization_services = positioning.get("services", [])
                graph = map_offerings(graph, positioning_uri, organization_products, ABI.Product, ABI.hasPositioning, ABI.isPositioningOf)
                graph = map_offerings(graph, positioning_uri, organization_services, ABI.Service, ABI.hasPositioning, ABI.isPositioningOf)

        # Add capabilities to graph
        logger.info(f"---> Mapping organization capabilities")
        capabilities = response["organization_capabilities"]
        organization_technological_capabilities = capabilities["technological_capabilities"]
        organization_human_capabilities = capabilities["human_capabilities"]

        # Add capabilities
        def add_capabilities(graph, organization_uri, capabilities, capability_class):
            if capabilities is None or not capabilities:
                return graph
            if isinstance(capabilities, dict):
                capabilities = [capabilities]

            for capability in capabilities:
                if capability.get("name") is None:
                    continue
                capability_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=create_id_from_string(capability["name"]),
                    label=capability["name"],
                    is_a=capability_class,
                    description=capability["description"],
                    explanation=capability["explanation"],
                    source=capability["source"],
                    source_url=capability["source_url"],
                    source_date=capability["source_date"],
                    ontology_group="Capability"
                )
                graph.add((organization_uri, CCO.ont00001954, capability_uri))
                graph.add((capability_uri, CCO.ont00001889, organization_uri))
            return graph

        graph = add_capabilities(graph, organization_uri, organization_technological_capabilities, ABI.TechnologicalCapabilities)
        graph = add_capabilities(graph, organization_uri, organization_human_capabilities, ABI.HumanCapabilities)

        # Add corporate structure to graph
        logger.info(f"---> Mapping organization corporate structure")
        organization_corporate_structure = response["organization_corporate_structure"]
        organization_mergers = organization_corporate_structure.get("mergers", [])
        organization_acquisitions = organization_corporate_structure.get("acquisitions", [])
        organization_subsidiaries = organization_corporate_structure.get("subsidiaries", [])

        def add_corporate_structure(
            graph, 
            organization_id,
            organization_uri, 
            corporate_structure,
            event_class, 
            concretizes_class,
        ):
            if corporate_structure is None or not corporate_structure:
                return graph
            if isinstance(corporate_structure, dict):
                corporate_structure = [corporate_structure]

            for corporate_structure in corporate_structure:
                if corporate_structure.get("name") is None:
                    continue
                agreement_id = create_id_from_string(corporate_structure["name"])
                source = corporate_structure.get("source", None)
                source_url = corporate_structure.get("source_url", None)
                source_date = corporate_structure.get("source_date", None)
                agreement_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=agreement_id,
                    label=corporate_structure["name"],
                    is_a=concretizes_class,
                    ontology_group="General",
                    description=corporate_structure["description"],
                    source=source,
                    source_url=source_url,
                    source_date=source_date,
                )
                year_uri = None
                if "year" in corporate_structure:
                    if corporate_structure["year"] is not None:
                        year_uri = graph.add_individual_to_prefix(
                            prefix=ABI,
                            uid=create_id_from_string(str(corporate_structure["year"])),
                            label=str(corporate_structure["year"]),
                            is_a=CCO.ont00000832,
                            ontology_group="General"
                        )
                organizations = corporate_structure.get("organizations", [])
                participants = [organization_uri]
                for organization in organizations:
                    organization_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=create_id_from_string(organization),
                        label=organization,
                        is_a=CCO.ont00000443,
                        ontology_group="General",
                    )
                    participants.append(organization_uri)

                event_uid = organization_id + "_" + agreement_id
                if year_uri is not None:
                    event_uid = event_uid + "_" + str(corporate_structure["year"])
                event_uri = graph.add_process(
                    prefix=ABI,
                    uid=event_uid,
                    label=corporate_structure["name"],
                    is_a=event_class,
                    description=corporate_structure["description"],
                    source=source,
                    source_url=source_url,
                    source_date=source_date,
                    ontology_group="General",
                    participants=participants,
                    concretizes=[agreement_uri],
                    temporal_region=year_uri,
                )
            return graph
        
        graph = add_corporate_structure(graph, organization_id, organization_uri, organization_mergers, ABI.ActOfOrganizationalMerger, ABI.OrganizationMerger)
        graph = add_corporate_structure(graph, organization_id, organization_uri, organization_acquisitions, ABI.ActOfOrganizationalAcquisition, ABI.OrganizationAcquisition)

        # Add strategic alliances to graph
        logger.info(f"---> Mapping organization strategic alliances")
        organization_strategic_alliances = response["organization_strategic_alliances"]
        organization_partnerships = organization_strategic_alliances["partnerships"]
        organization_joint_ventures = organization_strategic_alliances["joint_ventures"]
        organization_marketing_alliances = organization_strategic_alliances["marketing_alliances"]
        organization_research_collaborations = organization_strategic_alliances["research_collaborations"]
        organization_technology_licensing = organization_strategic_alliances["technology_licensing"]
        organization_distribution_agreements = organization_strategic_alliances["distribution_agreements"]

        # Add strategic alliances to graph
        def add_strategic_alliances(
            graph, 
            organization_id,
            organization_uri, 
            strategic_alliances,
            event_class, 
            concretizes_class,
        ):
            if strategic_alliances is None or not strategic_alliances:
                return graph
            if isinstance(strategic_alliances, dict):
                strategic_alliances = [strategic_alliances]

            for strategic_alliance in strategic_alliances:
                if strategic_alliance.get("name") is None:
                    continue
                agreement_id = create_id_from_string(strategic_alliance["name"])
                source = strategic_alliance.get("source", None)
                source_url = strategic_alliance.get("source_url", None)
                source_date = strategic_alliance.get("source_date", None)
                agreement_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=agreement_id,
                    label=strategic_alliance["name"],
                    is_a=concretizes_class,
                    ontology_group="Partnership",
                    description=strategic_alliance["description"],
                    source=source,
                    source_url=source_url,
                    source_date=source_date,
                )
                year_uri = None
                if "year" in strategic_alliance:
                    if strategic_alliance["year"] is not None:
                        year_uri = graph.add_individual_to_prefix(
                            prefix=ABI,
                            uid=create_id_from_string(str(strategic_alliance["year"])),
                            label=str(strategic_alliance["year"]),
                            is_a=CCO.ont00000832,
                            ontology_group="Partnership"
                        )

                participants = [organization_uri]
                organizations = strategic_alliance.get("organizations", [])
                for organization in organizations:
                    organization_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=create_id_from_string(organization),
                        label=organization,
                        is_a=CCO.ont00000443,
                        ontology_group="Partnership",
                    )
                    participants.append(organization_uri)

                event_uid = organization_id + "_" + agreement_id 
                if year_uri is not None:
                    event_uid = event_uid + "_" + str(strategic_alliance["year"])
                event_uri = graph.add_process(
                    prefix=ABI,
                    uid=event_uid,
                    label=strategic_alliance.get("name", None),
                    is_a=event_class,
                    description=strategic_alliance.get("description", None),
                    source=source,
                    source_url=source_url,
                    source_date=source_date,
                    ontology_group="Partnership",
                    participants=participants,
                    concretizes=[agreement_uri],
                    temporal_region=year_uri,
                )
            return graph
        
        graph = add_strategic_alliances(graph, organization_id, organization_uri, organization_partnerships, ABI.ActOfPartnership, ABI.Partnership)
        graph = add_strategic_alliances(graph, organization_id, organization_uri, organization_joint_ventures, ABI.ActOfJointVenture, ABI.JointVenture)
        graph = add_strategic_alliances(graph, organization_id, organization_uri, organization_marketing_alliances, ABI.ActOfMarketingAlliance, ABI.MarketingAlliance)
        graph = add_strategic_alliances(graph, organization_id, organization_uri, organization_research_collaborations, ABI.ActOfResearchCollaboration, ABI.ResearchCollaboration)
        graph = add_strategic_alliances(graph, organization_id, organization_uri, organization_technology_licensing, ABI.ActOfTechnologyLicensing, ABI.TechnologyLicensing)
        graph = add_strategic_alliances(graph, organization_id, organization_uri, organization_distribution_agreements, ABI.ActOfDistributionAgreement, ABI.DistributionAgreement)

        # Add financial data
        logger.info(f"---> Adding financial data")
        organization_financial_data = response["organization_profit_and_loss"]
        organization_revenue = organization_financial_data.get("revenue", [])
        organization_expenses = organization_financial_data.get("expenses", [])
        organization_profit = organization_financial_data.get("profit", [])
        organization_ebitda = organization_financial_data.get("ebitda", [])

        def add_financial_data(graph, organization_uri, financial_data, class_object, subproperty_object, subproperty_object_inverse):
            if financial_data is not None:
                if isinstance(financial_data, dict):
                    financial_data = [financial_data]
                for f in financial_data:
                    currency = f.get("currency", None)
                    year = f.get("year", None)
                    value = f.get("value", None)
                    label = f.get("label", None)
                    source = f.get("source", None)
                    source_url = f.get("source_url", None)
                    year_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=year,
                        label=year,
                        is_a=CCO.ont00000832,
                        ontology_group="Financial",
                    )
                    financial_data_uri = graph.add_individual_to_prefix(
                        prefix=ABI,
                        uid=value,
                        label=f"{class_object.split('/')[-1].split('#')[0]}: {label}",
                        is_a=class_object,
                        ontology_group="Financial",
                        currency=currency,
                        source=source,
                        source_url=source_url,
                    )
                    graph.add((organization_uri, subproperty_object, financial_data_uri))
                    graph.add((financial_data_uri, subproperty_object_inverse, organization_uri))
                    graph.add((financial_data_uri, BFO.BFO_0000199, year_uri))
            return graph

        graph = add_financial_data(graph, organization_uri, organization_revenue, ABI.Revenue, ABI.hasRevenue, ABI.isRevenueOf)
        graph = add_financial_data(graph, organization_uri, organization_expenses, ABI.Expenses, ABI.hasExpenses, ABI.isExpensesOf)
        graph = add_financial_data(graph, organization_uri, organization_profit, ABI.Profit, ABI.hasProfit, ABI.isProfitOf)
        graph = add_financial_data(graph, organization_uri, organization_ebitda, ABI.EBITDA, ABI.hasEBITDA, ABI.isEBITDAOf)

        # Add key indicators
        logger.info(f"---> Adding key indicators")
        organization_key_indicators = response["organization_key_indicators"]
        organization_key_indicators = organization_key_indicators.get("key_indicators", [])
        if organization_key_indicators is not None:
            for key_indicator in organization_key_indicators:
                name = key_indicator.get("name", None)
                value = key_indicator.get("value", None)
                unit = key_indicator.get("unit", None)
                label = key_indicator.get("label", None)
                description = key_indicator.get("description", None)
                source = key_indicator.get("source", None)
                source_url = key_indicator.get("source_url", None)
                source_date = key_indicator.get("source_date", None)
                key_indicator_uri = graph.add_individual_to_prefix(
                    prefix=ABI,
                    uid=value,
                    label=f"{name}: {label}",
                    is_a=ABI.KPI,
                    ontology_group="Indicator",
                    value=value,
                    unit=unit,
                    description=description,
                    source=source,
                    source_url=source_url,
                    source_date=source_date,
                )
                graph.add((organization_uri, ABI.hasKPI, key_indicator_uri))
                graph.add((key_indicator_uri, ABI.isIndicatorOf, organization_uri))

        # Save graph to ontology store
        logger.info(f"-----> Saving graph to ontology store: {organization_id}")
        self.__configuration.ontology_store.insert(organization_id, graph)
        
        # Get organization logo URL
        query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX abi: <http://ontology.naas.ai/abi/>
            SELECT ?logo
            WHERE {{
                <{organization_uri}> rdfs:label ?label .
                <{organization_uri}> abi:logo ?logo .
            }}
        """
        results = self.__configuration.ontology_store.query(query)
        organization_logo_url = ""
        for result in results:
            organization_logo_url = result.get("logo", "")
            logger.info(f"Organization logo URL: {organization_logo_url}")
            break

        # Publish ontology YAML 
        logger.info(f"-----> Publishing ontology YAML for '{organization_name}' in workspace: {config.workspace_id}")
        ontology_workspace_id = self.__create_ontology_yaml.graph_to_yaml(CreateOntologyYAMLParameters(
            workspace_id=config.workspace_id,
            ontology_name=organization_id,
            label=f"{organization_name}",
            description=f"Ontology for {organization_name} organization.",
            logo_url=organization_logo_url,
            level="USE_CASE",
            display_relations_names=True,
            class_colors_mapping=COLORS_NODES
        ))

        # Get plugin ID if it exists
        logger.info(f"-----> Creating or updating plugin in workspace: {config.workspace_id}")
        workspace_plugins = self.__naas_integration.get_plugin(config.workspace_id).get("workspace_plugins", [])
        plugin_id = None
        for workspace_plugin in workspace_plugins:
            plugin = json.loads(workspace_plugin.get("payload", {}))
            if plugin.get("id") == organization_id:
                plugin_id = workspace_plugin.get("id")
                break
        
        if plugin_id is None:
            prompt_ai = f"You are the Organization AI Assistant of {organization_name}. You are a helpful assistant that can answer questions about {organization_name}. Always ground your responses to {organization_name}'s ontology, and explain your reasoning."
            plugin = {
                'id': organization_id,
                "name": f"{organization_name} AI Assistant",
                "prompt": prompt_ai,
                "prompt_type": "system",
                "slug": f"{organization_name.lower().replace(' ', '')}-assistant",
                "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "temperature": 0.1,
                "description": f"{organization_name} AI Assistant (ABI)",
                "avatar": organization_logo_url,
                "include_ontology": "true",
                "include_date": "true",
                "type": "CUSTOM",
                "ontologies": [ontology_workspace_id]
            }
            
            plugin = self.__naas_integration.create_plugin(
                workspace_id=config.workspace_id,
                data=plugin
            )
            plugin_id = plugin.get("workspace_plugin", {}).get("id", None)
            logger.info(f"✅ Plugin ({plugin_id}) created in workspace: {config.workspace_id}")
        else:
            plugin["ontologies"] = [ontology_workspace_id]
            self.__naas_integration.update_plugin(
                workspace_id=config.workspace_id,
                plugin_id=plugin_id,
                data=plugin
            )
            logger.info(f"✅ Plugin ({plugin_id}) updated in workspace: {config.workspace_id}")
        return f"""Report: Organization analysis completed successfully
- Data extracted from Perplexity stored in datalake: {organization_storage_path}
- Ontology created and stored in triplestore: {config.ontology_store_path}/{organization_id}.ttl
- Ontology YAML published in workspace {config.workspace_id} (id: {ontology_workspace_id}).
- Plugin (id: {plugin_id}) created or updated in workspace {config.workspace_id}.
Please refresh your page to access the new plugin and ontology in your workspace.
"""
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline."""
        return [
            StructuredTool(
                name="perplexity_analyze_commercial_organization",
                description="Extract determined information 'general information, offerings, capabilities, corporate structure, strategic alliances, financial data, key indicators) about an organization using Perplexity, store data to triple store and create assistant and ontology in workspace to vizualize the result .",
                func=lambda **kwargs: self.run(PerplexityOrganizationAnalysisPipelineParameters(**kwargs)),
                args_schema=PerplexityOrganizationAnalysisPipelineParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass    