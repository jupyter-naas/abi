from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Annotated
from rdflib import URIRef, Literal, RDF, OWL, Graph, RDFS, XSD, Namespace
import os
import uuid
from datetime import datetime, timezone
from src.utils.Storage import get_excel, save_triples, save_excel
from src.utils.SPARQL import get_identifier
from abi.utils.String import create_hash_from_string
from abi.utils.Graph import ABI, CCO, BFO, URI_REGEX
from enum import Enum
from abi import logger
import pandas as pd

LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")

@dataclass
class LinkedInSalesNavigatorExportPipelineConfiguration(PipelineConfiguration):
    """Configuration for LinkedInSalesNavigatorExportPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service
        data_store_path (str): Path to the leadership data store
    """
    triple_store: ITripleStoreService
    data_store_path: str = "datastore/linkedin_sales_navigator/export"

class LinkedInSalesNavigatorExportPipelineParameters(PipelineParameters):
    """Parameters for LinkedInSalesNavigatorExportPipeline.
    
    Attributes:
        file_name (str): Name of the Excel file to process
        sheet_name (str): Name of the sheet to process
    """
    file_name: Annotated[str, Field(
        ..., 
        description="Name of the Excel file to process",
        example="SPF120_Executives.xlsx"
    )]
    sheet_name: Annotated[str, Field(
        default="Executives",
        description="Name of the sheet to process"
    )]
    init_organization_uri: Annotated[str, Field(
        ...,
        description="URI of the organization to initialize",
        pattern=URI_REGEX
    )]
    limit: Annotated[int | None, Field(
        default=None,
        description="Limit the number of rows to process"
    )]

class LinkedInSalesNavigatorExportPipeline(Pipeline):
    """Pipeline for importing data from Excel tables to the triple store."""
    
    __configuration: LinkedInSalesNavigatorExportPipelineConfiguration
    
    def __init__(self, configuration: LinkedInSalesNavigatorExportPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def _parse_time_duration(self, duration_str: str) -> int | None:
        """
        Converts a string like "X years Y months" into the number of months.
        For example, "7 years 5 months" -> 89 months.
        Returns the total number of months or prints a warning if the input is invalid.
        """
        
        # Split the string into tokens and find the number of years and months
        duration_tokens = duration_str.split()
        
        # Parse the duration string
        valid = False
        years = 0
        months = 0
        for i in range(len(duration_tokens)):
            if 'year' in duration_tokens[i]:
                if i > 0 and duration_tokens[i-1].isdigit():
                    years = int(duration_tokens[i-1])
                    valid = True
            elif 'month' in duration_tokens[i]:
                if i > 0 and duration_tokens[i-1].isdigit():
                    months = int(duration_tokens[i-1])
                    valid = True

        # If the input is invalid, return None
        if not valid:
            logger.debug(f"Warning: The input '{duration_str}' is invalid. Please provide data in the format 'nn years nn months' or 'nn years' or 'nn months'.")
            return None

        return years * 12 + months

    def calculate_start_date(self, duration_str: str) -> datetime | None:
        total_months = self._parse_time_duration(duration_str)
        if total_months is None:
            return None

        # Get the first day of the current month in UTC
        now = datetime.now(timezone.utc) 
        month_start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Subtract the duration in months
        start_date = pd.Timestamp(month_start_date) - pd.DateOffset(months=total_months)
        return start_date
    
    def generate_graph_date(self, date: datetime, date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> tuple[URIRef, Graph]:
        """Generates a URI for a date based on the given datetime object."""
        date_str = date.strftime(date_format)
        date_epoch = int(date.timestamp() * 1000)
        date_uri = ABI[str(date_epoch)]  # Create URI using timestamp
        graph = Graph()
        graph.add((date_uri, RDF.type, OWL.NamedIndividual))
        graph.add((date_uri, RDF.type, ABI.ISO8601UTCDateTime))
        graph.add((date_uri, RDFS.label, Literal(date_str, datatype=XSD.dateTime)))
        return date_uri, graph
        
    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, LinkedInSalesNavigatorExportPipelineParameters):
            raise ValueError("Parameters must be of type LinkedInSalesNavigatorExportPipelineParameters")
        
        # Init
        init_organization_uri = URIRef(parameters.init_organization_uri)

        # Read Excel file
        df = get_excel(
            self.__configuration.data_store_path, 
            parameters.file_name, 
            sheet_name=parameters.sheet_name,   
            skiprows=0,
        )
        if len(df) == 0:
            logger.error(f"❌ Excel file: {parameters.file_name}, sheet: {parameters.sheet_name}, rows: {len(df)}")
            return Graph()
        logger.info(f"🔍 Excel file: {parameters.file_name}, sheet: {parameters.sheet_name}, rows: {len(df)}")

        # Clean dataframe
        # df = df.dropna(subset=["Company"])
        # logger.info(f"🧹 Cleaned Excel file: {parameters.file_name}, sheet: {parameters.sheet_name}, rows: {len(df)}")
        df = df.fillna("")

        # Initialize graph
        graph_insert = Graph()
        graph_insert.bind("cco", CCO)
        graph_insert.bind("bfo", BFO)
        graph_insert.bind("abi", ABI)
        graph_insert.bind("rdfs", RDFS)
        graph_insert.bind("rdf", RDF)
        graph_insert.bind("owl", OWL)
        graph_insert.bind("xsd", XSD)

        # Define Class URIs
        PERSON = CCO["ont00001262"]
        LINKEDIN_PROFILE_PAGE = ABI["LinkedInProfilePage"]
        POSITION = BFO["BFO_0000023"]
        ORGANIZATION = CCO["ont00001180"]
        LINKEDIN_COMPANY_PAGE = ABI["LinkedInCompanyPage"]
        LOCATION = LINKEDIN["Location"]
        GROUP_OF_PERSONS = CCO["ont00000914"]
        ACT_OF_ASSOCIATION = CCO["ont00000433"]

        # Get file metadata
        file_path = os.path.join("storage", self.__configuration.data_store_path, parameters.file_name)
        file_timestamp = os.path.getmtime(file_path)
        file_datetime = datetime.fromtimestamp(file_timestamp)

        # Create backing datasource
        class_data_source_uri = URIRef("http://ontology.naas.ai/abi/DataSource")
        data_source_hash = create_hash_from_string(f"{file_timestamp}_{file_path}_{parameters.sheet_name}")
        data_source_uri = get_identifier(data_source_hash)
        if data_source_uri is None:
            data_source_uri = ABI[str(uuid.uuid4())]
            graph_insert.add((data_source_uri, RDF.type, OWL.NamedIndividual))
            graph_insert.add((data_source_uri, RDF.type, class_data_source_uri))
            graph_insert.add((data_source_uri, ABI.filename, Literal(parameters.file_name)))
            graph_insert.add((data_source_uri, ABI.sheet_name, Literal(parameters.sheet_name)))
            graph_insert.add((data_source_uri, ABI.unique_id, Literal(data_source_hash)))
            graph_insert.add((data_source_uri, ABI.extracted_at, Literal(file_datetime.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
            graph_insert.add((data_source_uri, ABI.source_path, Literal(file_path)))
            graph_insert.add((data_source_uri, ABI.source_type, Literal("EXCEL_FILE")))
        else:
            data_source_uri = URIRef(data_source_uri)
        
        # Process each row
        logger.info(f"Processing {len(df)} rows")
        count_row: int = 0
        linkedin_profile_page_uris: dict[str, URIRef] = {}
        position_uris: dict[str, URIRef] = {}
        organization_uris: dict[str, URIRef] = {}
        linkedin_company_page_uris: dict[str, URIRef] = {}
        leadership_group_of_persons_uris: dict[str, URIRef] = {}
        location_uris: dict[str, URIRef] = {}
        for i, row in df[:parameters.limit].iterrows():
            count_row += 1
            logger.info(f"==> Processing row {count_row}/{len(df)}: {tuple(row)}")
            row_hash = create_hash_from_string(str(tuple(row)))
            row_uri = get_identifier(row_hash)
            if row_uri is None:
                row_uri = ABI[str(uuid.uuid4())]
                # Add backing datasource component
                graph_insert.add((row_uri, RDF.type, OWL.NamedIndividual))
                graph_insert.add((row_uri, RDF.type, URIRef("http://ontology.naas.ai/abi/DataSourceComponent")))
                graph_insert.add((row_uri, ABI.unique_id, Literal(row_hash)))
                graph_insert.add((row_uri, ABI.isComponentOf, data_source_uri))
                graph_insert.add((data_source_uri, ABI.hasComponent, row_uri))
            else:
                logger.info(f"Skipping row {tuple(row)}")
                continue

            # Add person
            # person_name = " ".join(word.capitalize() for word in row.get("Name", "").strip().split(" "))
            person_name = row.get("Name", "").strip()
            person_uri = ABI[str(uuid.uuid4())]
            graph_insert.add((person_uri, RDF.type, OWL.NamedIndividual))
            graph_insert.add((person_uri, RDF.type, PERSON))
            graph_insert.add((person_uri, RDFS.label, Literal(person_name)))
            graph_insert.add((person_uri, ABI.hasBackingDataSource, row_uri))

            # Add LinkedIn company page
            lk_sales_navigator_linkedin_url = row.get("LinkedIn URL", "").strip()
            linkedin_profile_url = None
            if lk_sales_navigator_linkedin_url != "":
                lk_linkedin_id = lk_sales_navigator_linkedin_url.split("/lead/")[1].split(",")[0]
                linkedin_profile_url = f"https://www.linkedin.com/in/{lk_linkedin_id}"
            lk_profile_hash = create_hash_from_string(lk_linkedin_id)
            if lk_profile_hash in linkedin_profile_page_uris: # Optimize: if linkedin profile page already exists, use it -> avoid SPARQL query
                linkedin_profile_page_uri = linkedin_profile_page_uris.get(lk_profile_hash)
            else:
                linkedin_profile_page_uri = get_identifier(lk_profile_hash)

            # Create linkedin profile page if it doesn't exist
            if linkedin_profile_page_uri is None:
                linkedin_profile_page_uri = ABI[str(uuid.uuid4())]
                linkedin_profile_page_uris[lk_profile_hash] = linkedin_profile_page_uri
                graph_insert.add((linkedin_profile_page_uri, RDF.type, OWL.NamedIndividual))
                graph_insert.add((linkedin_profile_page_uri, RDF.type, LINKEDIN_PROFILE_PAGE))
                graph_insert.add((linkedin_profile_page_uri, RDFS.label, Literal(linkedin_profile_url)))
                graph_insert.add((linkedin_profile_page_uri, ABI.unique_id, Literal(lk_profile_hash)))
                graph_insert.add((linkedin_profile_page_uri, ABI.linkedin_url, Literal(linkedin_profile_url)))
                graph_insert.add((linkedin_profile_page_uri, ABI.linkedin_id, Literal(lk_linkedin_id)))
                graph_insert.add((linkedin_profile_page_uri, ABI.isLinkedInPageOf, person_uri))
                graph_insert.add((person_uri, ABI.hasLinkedInPage, linkedin_profile_page_uri))
                graph_insert.add((linkedin_profile_page_uri, ABI.hasBackingDataSource, row_uri))

            # Add position
            position = row.get("Job Title", "").strip()
            position_hash = create_hash_from_string(position)
            if position_hash in position_uris: # Optimize: if position already exists, use it -> avoid SPARQL query
                position_uri = position_uris.get(position_hash)
            else:
                position_uri = get_identifier(position_hash)

            # Create position if it doesn't exist
            if position_uri is None:
                position_uri = ABI[str(uuid.uuid4())]
                position_uris[position_hash] = position_uri
                graph_insert.add((position_uri, RDF.type, OWL.NamedIndividual))
                graph_insert.add((position_uri, RDF.type, POSITION))
                graph_insert.add((position_uri, RDFS.label, Literal(position)))
                graph_insert.add((position_uri, ABI.unique_id, Literal(position_hash)))
                graph_insert.add((person_uri, ABI.holdsPosition, position_uri))
                graph_insert.add((position_uri, ABI.hasBackingDataSource, row_uri))

            # Add organization & linkedin company page
            organization = row.get("Company", "").strip()
            lk_sales_navigator_company_url = row.get("Company URL", "").strip()
            linkedin_company_page_url = None
            if lk_sales_navigator_company_url != "":
                lk_company_id = lk_sales_navigator_company_url.split("/company/")[1].split("?")[0]
                linkedin_company_page_url = f"https://www.linkedin.com/company/{lk_company_id}"
            if organization != "":
                organization_hash = create_hash_from_string(organization)
                if organization_hash in organization_uris: # Optimize: if organization already exists, use it -> avoid SPARQL query
                    organization_uri = organization_uris.get(organization_hash)
                else:
                    organization_uri = get_identifier(organization_hash)

                # Create organization if it doesn't exist
                if organization_uri is None:
                    organization_uri = ABI[str(uuid.uuid4())]
                    organization_uris[organization_hash] = organization_uri
                    graph_insert.add((organization_uri, RDF.type, OWL.NamedIndividual))
                    graph_insert.add((organization_uri, RDF.type, ORGANIZATION))
                    graph_insert.add((organization_uri, RDFS.label, Literal(organization)))
                    graph_insert.add((organization_uri, CCO.ont00001977, init_organization_uri))
                    graph_insert.add((organization_uri, ABI.hasBackingDataSource, row_uri))

                # Add LinkedIn company page
                lk_company_hash = create_hash_from_string(lk_company_id)
                if lk_company_hash in linkedin_company_page_uris: # Optimize: if linkedin company page already exists, use it -> avoid SPARQL query
                    linkedin_company_page_uri = linkedin_company_page_uris.get(lk_company_hash)
                else:
                    linkedin_company_page_uri = get_identifier(lk_company_hash)

                # Create linkedin company page if it doesn't exist
                if linkedin_company_page_uri is None:
                    linkedin_company_page_uri = ABI[str(uuid.uuid4())]
                    linkedin_company_page_uris[lk_company_hash] = linkedin_company_page_uri
                    graph_insert.add((linkedin_company_page_uri, RDF.type, OWL.NamedIndividual))
                    graph_insert.add((linkedin_company_page_uri, RDF.type, LINKEDIN_COMPANY_PAGE))
                    graph_insert.add((linkedin_company_page_uri, RDFS.label, Literal(linkedin_company_page_url)))
                    graph_insert.add((linkedin_company_page_uri, ABI.unique_id, Literal(lk_company_hash)))
                    graph_insert.add((linkedin_company_page_uri, ABI.linkedin_url, Literal(linkedin_company_page_url)))
                    graph_insert.add((linkedin_company_page_uri, ABI.linkedin_id, Literal(lk_company_id)))
                    graph_insert.add((linkedin_company_page_uri, ABI.isLinkedInPageOf, organization_uri))
                    graph_insert.add((organization_uri, ABI.hasLinkedInPage, linkedin_company_page_uri))
                    graph_insert.add((linkedin_company_page_uri, ABI.hasBackingDataSource, row_uri))

                # Add group label
                group_of_persons_label = f"{organization} Leadership"
                group_of_persons_hash = create_hash_from_string(group_of_persons_label)
                if group_of_persons_hash in leadership_group_of_persons_uris: # Optimize: if group of persons already exists, use it -> avoid SPARQL query
                    group_of_persons_uri = leadership_group_of_persons_uris.get(group_of_persons_hash)
                else:
                    group_of_persons_uri = get_identifier(group_of_persons_hash)

                # Create group of persons if it doesn't exist
                if group_of_persons_uri is None:
                    group_of_persons_uri = ABI[str(uuid.uuid4())]
                    leadership_group_of_persons_uris[group_of_persons_hash] = group_of_persons_uri
                    graph_insert.add((group_of_persons_uri, RDF.type, OWL.NamedIndividual))
                    graph_insert.add((group_of_persons_uri, RDF.type, GROUP_OF_PERSONS))
                    graph_insert.add((group_of_persons_uri, RDFS.label, Literal(group_of_persons_label)))
                    graph_insert.add((group_of_persons_uri, ABI.unique_id, Literal(group_of_persons_hash)))
                    graph_insert.add((group_of_persons_uri, CCO.ont00001977, person_uri))
                    graph_insert.add((group_of_persons_uri, ABI.hasPosition, position_uri))
                    graph_insert.add((group_of_persons_uri, ABI.hasBackingDataSource, row_uri))
                    graph_insert.add((organization_uri, BFO.BFO_0000115, group_of_persons_uri))    

                # Create act of association
                time_in_role = row.get("Time in Role", "0 months in role")  # Get Time in Role
                time_in_company = row.get("Time in Company", "0 months in company")  # Get Time in Company

                # Calculate actual start dates for role and company
                print("Time in role: ", time_in_role)
                print("Time in company: ", time_in_company)
                time_in_role_start_date = self.calculate_start_date(time_in_role)
                time_in_company_start_date = self.calculate_start_date(time_in_company)
                print("Time in role start date: ", time_in_role_start_date)
                print("Time in company start date: ", time_in_company_start_date)

                # Generate time URIs for StartDate
                if time_in_role_start_date is not None:
                    time_in_role_uri, graph_time_in_role = self.generate_graph_date(time_in_role_start_date)
                    graph_insert += graph_time_in_role
                if time_in_company_start_date is not None:
                    time_in_company_uri, graph_time_in_company = self.generate_graph_date(time_in_company_start_date)
                    graph_insert += graph_time_in_company

                # Create act of association with organization and role
                act_of_association_label = f"{person_name} working at {organization} as {position}"
                act_of_association_hash = create_hash_from_string(act_of_association_label)
                act_of_association_uri = get_identifier(act_of_association_hash)
                if act_of_association_uri is None:
                    act_of_association_uri = ABI[str(uuid.uuid4())]
                    graph_insert.add((act_of_association_uri, RDF.type, OWL.NamedIndividual))
                    graph_insert.add((act_of_association_uri, RDF.type, OWL.NamedIndividual))
                    graph_insert.add((act_of_association_uri, RDF.type, ACT_OF_ASSOCIATION))
                    graph_insert.add((act_of_association_uri, RDFS.label, Literal(act_of_association_label)))
                    graph_insert.add((act_of_association_uri, ABI.unique_id, Literal(act_of_association_hash)))
                    graph_insert.add((act_of_association_uri, BFO.BFO_0000057, organization_uri))
                    graph_insert.add((act_of_association_uri, BFO.BFO_0000057, person_uri))
                    graph_insert.add((act_of_association_uri, BFO.BFO_0000055, position_uri))
                    graph_insert.add((act_of_association_uri, BFO.BFO_0000108, Literal(file_datetime.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
                    if time_in_role_uri is not None:
                        graph_insert.add((act_of_association_uri, ABI.startDate, time_in_role_uri))
                    graph_insert.add((act_of_association_uri, ABI.hasBackingDataSource, row_uri))

                # Create act of association with organization and role
                act_of_association_label_2 = f"{person_name} working at {organization}"
                act_of_association_hash_2 = create_hash_from_string(act_of_association_label_2)
                act_of_association_uri_2 = get_identifier(act_of_association_hash_2)
                if act_of_association_uri_2 is None:
                    act_of_association_uri_2 = ABI[str(uuid.uuid4())]
                    graph_insert.add((act_of_association_uri_2, RDF.type, OWL.NamedIndividual))
                    graph_insert.add((act_of_association_uri_2, RDF.type, OWL.NamedIndividual))
                    graph_insert.add((act_of_association_uri_2, RDF.type, ACT_OF_ASSOCIATION))
                    graph_insert.add((act_of_association_uri_2, RDFS.label, Literal(act_of_association_label_2)))
                    graph_insert.add((act_of_association_uri_2, ABI.unique_id, Literal(act_of_association_hash_2)))
                    graph_insert.add((act_of_association_uri_2, BFO.BFO_0000057, organization_uri))
                    graph_insert.add((act_of_association_uri_2, BFO.BFO_0000057, person_uri))
                    graph_insert.add((act_of_association_uri_2, BFO.BFO_0000108, Literal(file_datetime.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
                    if time_in_company_uri is not None:
                        graph_insert.add((act_of_association_uri_2, ABI.startDate, time_in_company_uri))
                    graph_insert.add((act_of_association_uri_2, ABI.hasBackingDataSource, row_uri))
                    graph_insert.add((act_of_association_uri_2, BFO.BFO_0000117, act_of_association_uri)) #has occurrent part
                    graph_insert.add((act_of_association_uri, BFO.BFO_0000132, act_of_association_uri_2)) # occurrent part of

            # Add location
            location = row.get("Location", "").strip()
            lk_location_hash = create_hash_from_string(location)
            if lk_location_hash in location_uris: # Optimize: if location already exists, use it -> avoid SPARQL query
                location_uri = location_uris.get(lk_location_hash)
            else:
                location_uri = get_identifier(lk_location_hash)

            # Create location if it doesn't exist
            if location_uri is None:
                location_uri = ABI[str(uuid.uuid4())]
                location_uris[lk_location_hash] = location_uri
                graph_insert.add((location_uri, RDF.type, OWL.NamedIndividual))
                graph_insert.add((location_uri, RDF.type, LOCATION))
                graph_insert.add((location_uri, RDFS.label, Literal(location)))
                graph_insert.add((location_uri, ABI.unique_id, Literal(lk_location_hash)))
                graph_insert.add((location_uri, ABI.hasBackingDataSource, row_uri))
                graph_insert.add((location_uri, BFO.BFO_0000124, person_uri)) # location of
                graph_insert.add((person_uri, BFO.BFO_0000171, location_uri)) # located in

        # Save to triple store
        dir_excel_path = os.path.join(
            self.__configuration.data_store_path, 
            parameters.file_name.split(".")[0]
        )
        if len(graph_insert) > 0:
            # self.__configuration.triple_store.insert(graph_insert)
            save_triples(
                graph_insert, 
                os.path.join(
                    dir_excel_path,
                    parameters.sheet_name
                ), 
                f"insert_{parameters.file_name}_{parameters.sheet_name}.ttl"
            )
        if len(graph_insert) > 0:
            save_excel(
                df, 
                os.path.join(
                    dir_excel_path,
                    parameters.sheet_name
                ), 
                parameters.file_name.split(".")[0]  + "_" + parameters.sheet_name + ".xlsx",
                parameters.sheet_name
            )
        return graph_insert
    
    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="export_linkedin_sales_navigator_to_triple_store",
                description="Export LinkedIn Sales Navigator data to the triple store",
                func=lambda **kwargs: self.run(LinkedInSalesNavigatorExportPipelineParameters(**kwargs)),
                args_schema=LinkedInSalesNavigatorExportPipelineParameters
            )   
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None
