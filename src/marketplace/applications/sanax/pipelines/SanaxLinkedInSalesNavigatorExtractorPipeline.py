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
from src.utils.SPARQL import get_identifiers
from abi.utils.String import create_hash_from_string
from abi.utils.Graph import ABI, CCO, BFO
from enum import Enum
from abi import logger
import pandas as pd


LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")


@dataclass
class SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(PipelineConfiguration):
    """Configuration for LinkedInSalesNavigatorExportPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service
        data_store_path (str): Path to the leadership data store
    """
    triple_store: ITripleStoreService
    data_store_path: str = "datastore/sanax/linkedin_sales_navigator"
    limit: int | None = None


class SanaxLinkedInSalesNavigatorExtractorPipelineParameters(PipelineParameters):
    """Parameters for LinkedInSalesNavigatorExportPipeline.
    
    This pipeline processes Excel files that contain LinkedIn Sales Navigator user data extracted using 
    the Sanax Chrome extension (https://chromewebstore.google.com/detail/sanax-linkedin-sales-navi/mfagglhpdadnjghfbodblpdhgnekalad).
    The extension allows automated extraction of Sales Navigator search results into Excel format.
    
    Attributes:
        file_path (str): Path of the Excel file to process
        sheet_name (str): Name of the sheet to process
    """
    file_path: Annotated[str, Field(
        description="Path of the Excel file to process",
        example="datastore/linkedin_sales_navigator/sanax_extractor/Example.xlsx"
    )]
    sheet_name: Annotated[str, Field(
        description="Name of the sheet to process"
    )] = "LinkedIn Sales Navigator"


class SanaxLinkedInSalesNavigatorExtractorPipeline(Pipeline):
    """Pipeline for importing data from Excel tables to the triple store."""
    
    __configuration: SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration
    

    def __init__(self, configuration: SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration):
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
            logger.warning(f"Warning: The input '{duration_str}' is invalid. Please provide data in the format 'nn years nn months' or 'nn years' or 'nn months'.")
            return None

        return years * 12 + months


    def calculate_start_date(self, duration_str: str, start_datetime: datetime | None = None) -> datetime | None:
        total_months = self._parse_time_duration(duration_str)
        if total_months is None:
            return None

        # Get the first day of the current month in UTC
        if start_datetime is None:
            start_datetime = datetime.now(timezone.utc) 
        month_start_date = start_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
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
        
        
    def _read_and_validate_excel(self, parameters: SanaxLinkedInSalesNavigatorExtractorPipelineParameters) -> pd.DataFrame:
        """Read and validate Excel file containing LinkedIn Sales Navigator data.
        
        Args:
            parameters: Parameters containing file path and sheet name
            
        Returns:
            DataFrame containing the validated Excel data
            
        Raises:
            ValueError: If required columns are missing
            FileNotFoundError: If file cannot be found locally or in storage
        """
        # Required columns
        required_columns: list = [
            'Name', 
            'Job Title', 
            'Company', 
            'Company URL', 
            'Location',
            'Time in Role',
            'Time in Company', 
            'LinkedIn URL'
        ]
        file_path = self.__clean_file_path(parameters.file_path)
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        sheet_name = parameters.sheet_name

        try:
            df = get_excel(
                dir_path,
                file_name,
                sheet_name=sheet_name,
                skiprows=0,
            )
            logger.debug(f"✅ Successfully read file from storage: {file_path}")
        except Exception as e:
            logger.error(f"❌ File not found in storage: {e}")
            
        # Try to read locally next
        if len(df) == 0:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=0)
                logger.debug(f"✅ Successfully read local file: {file_path}")
                        
            except Exception as e:
                logger.error(f"❌ File not found locally: {e}")

        # Validate file is not empty
        if len(df) == 0:
            logger.error(f"❌ Excel file: {file_path}, sheet: {sheet_name}, rows: {len(df)}")
            return pd.DataFrame()
        df = df.fillna("") # Clean dataframe
        logger.debug(f"✅ Rows to be processed: {len(df)}")

        # Validate required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.error(f"❌ Missing required columns in Excel file: {missing_columns}")
            return pd.DataFrame()
        logger.debug(f"✅ Validated {len(required_columns)} required columns in Excel file")
        
        return df
    
    def __clean_file_path(self, file_path: str) -> str:
        if file_path.startswith("storage"):
            return file_path[len("storage")+1:]
        return file_path

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, SanaxLinkedInSalesNavigatorExtractorPipelineParameters):
            raise ValueError("Parameters must be of type SanaxLinkedInSalesNavigatorExtractorPipelineParameters")

        # Step 1: Read Excel file
        file_path = self.__clean_file_path(parameters.file_path)
        logger.debug(f"Step 1: Reading Excel file '{file_path}' with sheet name '{parameters.sheet_name}'")
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        df = self._read_and_validate_excel(parameters)
        if len(df) == 0:
            return Graph()

        # Step 2: Initializing graph and creating backing datasource
        logger.debug("Step 2: Initializing graph and creating backing datasource")
        graph = Graph()
        graph.bind("cco", CCO)
        graph.bind("bfo", BFO)
        graph.bind("abi", ABI)
        graph.bind("rdfs", RDFS)
        graph.bind("rdf", RDF)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)

        # Define Class URIs
        PERSON = CCO["ont00001262"]
        LINKEDIN_PROFILE_PAGE = LINKEDIN["ProfilePage"]
        POSITION = BFO["BFO_0000023"]
        ORGANIZATION = CCO["ont00001180"]
        LINKEDIN_COMPANY_PAGE = LINKEDIN["CompanyPage"]
        LOCATION = LINKEDIN["Location"]
        ACT_OF_ASSOCIATION = CCO["ont00000433"]

        # Get file metadata
        file_path = os.path.join("storage", dir_path, file_name)
        file_timestamp = os.path.getmtime(file_path)
        file_datetime = datetime.fromtimestamp(file_timestamp)
        logger.debug(f"File modified at: {file_datetime}")

        # Get unique identifiers
        unique_identifiers: dict[str, URIRef] = get_identifiers()
        logger.debug(f"Unique identifiers: {len(unique_identifiers)}")

        # Create backing datasource
        class_data_source_uri = URIRef("http://ontology.naas.ai/abi/DataSource")
        data_source_hash = create_hash_from_string(f"{file_timestamp}_{file_path}_{parameters.sheet_name}")
        data_source_uri = unique_identifiers.get(data_source_hash)
        if data_source_uri is None:
            data_source_uri = ABI[str(uuid.uuid4())]
            graph.add((data_source_uri, RDF.type, OWL.NamedIndividual))
            graph.add((data_source_uri, RDF.type, class_data_source_uri))
            graph.add((data_source_uri, ABI.filename, Literal(file_name)))
            graph.add((data_source_uri, ABI.sheet_name, Literal(parameters.sheet_name)))
            graph.add((data_source_uri, ABI.unique_id, Literal(data_source_hash)))
            graph.add((data_source_uri, ABI.extracted_at, Literal(file_datetime.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
            graph.add((data_source_uri, ABI.source_path, Literal(file_path)))
            graph.add((data_source_uri, ABI.source_type, Literal("EXCEL_FILE")))
        
        # Step 3: Processing rows from Excel file
        logger.debug("Step 3: Processing rows")
        count_row: int = 0
        linkedin_profile_page_uris: dict[str, URIRef] = get_identifiers(class_uri=LINKEDIN_PROFILE_PAGE)
        logger.debug(f"- Existing LinkedIn profile page: {len(linkedin_profile_page_uris)}")
        person_uris: dict[str, URIRef] = get_identifiers(RDFS.label, class_uri=PERSON)
        logger.debug(f"- Existing Person: {len(person_uris)}")
        position_uris: dict[str, URIRef] = get_identifiers(class_uri=POSITION)
        logger.debug(f"- Existing Positions: {len(position_uris)}")
        organization_uris: dict[str, URIRef] = get_identifiers(RDFS.label, class_uri=ORGANIZATION)
        logger.debug(f"- Existing Organization: {len(organization_uris)}")
        linkedin_company_page_uris: dict[str, URIRef] = get_identifiers(class_uri=LINKEDIN_COMPANY_PAGE)
        logger.debug(f"- Existing LinkedIn company page: {len(linkedin_company_page_uris)}")
        location_uris: dict[str, URIRef] = get_identifiers(class_uri=LOCATION)
        logger.debug(f"- Existing Location: {len(location_uris)}")
        if self.__configuration.limit is not None:
            df = df[:self.__configuration.limit]

        for i, row in df.iterrows():
            count_row += 1
            logger.debug(f"🔄 Processing row {count_row}/{len(df)}")
            row_hash = create_hash_from_string(str(tuple(row)))
            row_uri = unique_identifiers.get(row_hash)
            if row_uri is None:
                logger.debug("Step 3.1: Adding backing datasource component for row")
                row_uri = ABI[str(uuid.uuid4())]
                # Add backing datasource component
                graph.add((row_uri, RDF.type, OWL.NamedIndividual))
                graph.add((row_uri, RDF.type, URIRef("http://ontology.naas.ai/abi/DataSourceComponent")))
                graph.add((row_uri, ABI.unique_id, Literal(row_hash)))
                graph.add((row_uri, ABI.isComponentOf, data_source_uri))
                graph.add((data_source_uri, ABI.hasComponent, row_uri))
            else:
                logger.warning("Row already processed!")
                continue

            # Add LinkedIn profile page
            lk_sales_navigator_linkedin_url = row.get("LinkedIn URL", "").strip()
            linkedin_profile_url = None
            if lk_sales_navigator_linkedin_url != "":
                lk_linkedin_id = lk_sales_navigator_linkedin_url.split("/lead/")[1].split(",")[0]
                linkedin_profile_url = f"https://www.linkedin.com/in/{lk_linkedin_id}"
            logger.debug(f"Step 3.2: Adding LinkedIn profile page: '{linkedin_profile_url}'")
            lk_profile_hash = create_hash_from_string(lk_linkedin_id)
            linkedin_profile_page_uri = linkedin_profile_page_uris.get(lk_profile_hash)

            # Create linkedin profile page if it doesn't exist
            if linkedin_profile_page_uri is None:
                linkedin_profile_page_uri = ABI[str(uuid.uuid4())]
                linkedin_profile_page_uris[lk_profile_hash] = linkedin_profile_page_uri
                graph.add((linkedin_profile_page_uri, RDF.type, OWL.NamedIndividual))
                graph.add((linkedin_profile_page_uri, RDF.type, LINKEDIN_PROFILE_PAGE))
                graph.add((linkedin_profile_page_uri, RDFS.label, Literal(linkedin_profile_url)))
                graph.add((linkedin_profile_page_uri, ABI.unique_id, Literal(lk_profile_hash)))
                graph.add((linkedin_profile_page_uri, ABI.linkedin_url, Literal(linkedin_profile_url)))
                graph.add((linkedin_profile_page_uri, ABI.linkedin_id, Literal(lk_linkedin_id)))
                graph.add((linkedin_profile_page_uri, ABI.hasBackingDataSource, row_uri))
            else:
                logger.warning("LinkedIn profile page already processed!")
                continue

            # Add person to the graph
            person_name = row.get("Name", "").strip()
            logger.debug(f"Step 3.3: Adding person '{person_name}'")
            person_uri = person_uris.get(person_name)
            if person_uri is None:
                person_uri = ABI[str(uuid.uuid4())]
                person_uris[person_name] = person_uri
                graph.add((person_uri, RDF.type, OWL.NamedIndividual))
                graph.add((person_uri, RDF.type, PERSON))
                graph.add((person_uri, RDFS.label, Literal(person_name)))
                graph.add((person_uri, ABI.hasBackingDataSource, row_uri))
            graph.add((linkedin_profile_page_uri, ABI.isLinkedInPageOf, person_uri))
            graph.add((person_uri, ABI.hasLinkedInPage, linkedin_profile_page_uri))

            # Add location
            location = row.get("Location", "").strip()
            logger.debug(f"Step 3.4: Adding location: '{location}'")
            lk_location_hash = create_hash_from_string(location)
            location_uri = location_uris.get(lk_location_hash) if location != "" else None

            # Create location if it doesn't exist
            if location_uri is None:
                location_uri = ABI[str(uuid.uuid4())]
                location_uris[lk_location_hash] = location_uri
                graph.add((location_uri, RDF.type, OWL.NamedIndividual))
                graph.add((location_uri, RDF.type, LOCATION))
                graph.add((location_uri, RDFS.label, Literal(location)))
                graph.add((location_uri, ABI.unique_id, Literal(lk_location_hash)))
                graph.add((location_uri, ABI.hasBackingDataSource, row_uri))
            graph.add((location_uri, BFO.BFO_0000124, person_uri)) # location of
            graph.add((person_uri, BFO.BFO_0000171, location_uri)) # located in

            # Add position
            position = row.get("Job Title", "").strip()
            logger.debug(f"Step 3.5: Adding position: '{position}'")
            position_hash = create_hash_from_string(position)
            position_uri = position_uris.get(position_hash) if position != "" else None
            
            # Create position if it doesn't exist
            if position_uri is None:
                position_uri = ABI[str(uuid.uuid4())]
                position_uris[position_hash] = position_uri
                graph.add((position_uri, RDF.type, OWL.NamedIndividual))
                graph.add((position_uri, RDF.type, POSITION))
                graph.add((position_uri, RDFS.label, Literal(position)))
                graph.add((position_uri, ABI.unique_id, Literal(position_hash)))
                graph.add((position_uri, ABI.hasBackingDataSource, row_uri))
            graph.add((person_uri, ABI.holdsPosition, position_uri))

            # Add organization & linkedin company page
            organization = row.get("Company", "").strip()
            logger.debug(f"Step 3.6: Adding organization: '{organization}'")
            organization_uri = organization_uris.get(organization) if organization != "" else None
            # Create organization if it doesn't exist
            if organization_uri is None and organization != "":
                organization_uri = ABI[str(uuid.uuid4())]
                organization_uris[organization] = organization_uri
                graph.add((organization_uri, RDF.type, OWL.NamedIndividual))
                graph.add((organization_uri, RDF.type, ORGANIZATION))
                graph.add((organization_uri, RDFS.label, Literal(organization)))
                graph.add((organization_uri, ABI.hasBackingDataSource, row_uri))

            # Add LinkedIn company page
            lk_sales_navigator_company_url = row.get("Company URL", "").strip()
            lk_company_id = None
            linkedin_company_page_url = None
            if lk_sales_navigator_company_url != "" and "/company/" in lk_sales_navigator_company_url:
                lk_company_id = lk_sales_navigator_company_url.split("/company/")[1].split("?")[0]
                linkedin_company_page_url = f"https://www.linkedin.com/company/{lk_company_id}"

            
            if lk_company_id is not None:
                logger.debug(f"Step 3.7: Adding LinkedIn company page: '{linkedin_company_page_url}'")
                lk_company_hash = create_hash_from_string(lk_company_id)
                linkedin_company_page_uri = linkedin_company_page_uris.get(lk_company_hash)

                # Create linkedin company page if it doesn't exist
                if linkedin_company_page_uri is None:
                    linkedin_company_page_uri = ABI[str(uuid.uuid4())]
                    linkedin_company_page_uris[lk_company_hash] = linkedin_company_page_uri
                    graph.add((linkedin_company_page_uri, RDF.type, OWL.NamedIndividual))
                    graph.add((linkedin_company_page_uri, RDF.type, LINKEDIN_COMPANY_PAGE))
                    graph.add((linkedin_company_page_uri, RDFS.label, Literal(linkedin_company_page_url)))
                    graph.add((linkedin_company_page_uri, ABI.unique_id, Literal(lk_company_hash)))
                    graph.add((linkedin_company_page_uri, ABI.linkedin_url, Literal(linkedin_company_page_url)))
                    graph.add((linkedin_company_page_uri, ABI.linkedin_id, Literal(lk_company_id)))
                    graph.add((linkedin_company_page_uri, ABI.hasBackingDataSource, row_uri))

                    if organization_uri is not None:
                        graph.add((linkedin_company_page_uri, ABI.isLinkedInPageOf, organization_uri))
                        graph.add((organization_uri, ABI.hasLinkedInPage, linkedin_company_page_uri))

            # Create act of association
            time_in_role = row.get("Time in Role", "0 months in role")  # Get Time in Role
            time_in_company = row.get("Time in Company", "0 months in company")  # Get Time in Company

            # Calculate actual start dates for role and company
            time_in_role_start_date = self.calculate_start_date(time_in_role, file_datetime)
            time_in_company_start_date = self.calculate_start_date(time_in_company, file_datetime)

            # Generate time URIs for StartDate
            if time_in_role_start_date is not None:
                time_in_role_uri, graph_time_in_role = self.generate_graph_date(time_in_role_start_date)
                graph += graph_time_in_role
            if time_in_company_start_date is not None:
                time_in_company_uri, graph_time_in_company = self.generate_graph_date(time_in_company_start_date)
                graph += graph_time_in_company

            # Create act of association with organization and role
            act_of_association_label = f"{person_name} working at {organization} as {position}"
            act_of_association_hash = create_hash_from_string(act_of_association_label)
            logger.debug(f"Step 3.8: Adding act of association with organization and role: '{act_of_association_label}'")
            act_of_association_uri = ABI[str(uuid.uuid4())]
            graph.add((act_of_association_uri, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri, RDF.type, ACT_OF_ASSOCIATION))
            graph.add((act_of_association_uri, RDFS.label, Literal(act_of_association_label)))
            graph.add((act_of_association_uri, ABI.unique_id, Literal(act_of_association_hash)))
            graph.add((act_of_association_uri, ABI.hasBackingDataSource, row_uri))
            graph.add((act_of_association_uri, BFO.BFO_0000108, Literal(file_datetime.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
            if organization_uri is not None:
                graph.add((act_of_association_uri, BFO.BFO_0000057, organization_uri))
            if person_uri is not None:
                graph.add((act_of_association_uri, BFO.BFO_0000057, person_uri))
            if position_uri is not None:
                graph.add((act_of_association_uri, BFO.BFO_0000055, position_uri))
            if time_in_role_uri is not None:
                graph.add((act_of_association_uri, ABI.startDate, time_in_role_uri))
            
            # Create act of association with organization and role
            act_of_association_label_2 = f"{person_name} working at {organization}"
            act_of_association_hash_2 = create_hash_from_string(act_of_association_label_2)
            logger.debug(f"Step 3.9: Adding act of association with organization: '{act_of_association_label_2}'")
            act_of_association_uri_2 = ABI[str(uuid.uuid4())]
            graph.add((act_of_association_uri_2, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri_2, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri_2, RDF.type, ACT_OF_ASSOCIATION))
            graph.add((act_of_association_uri_2, RDFS.label, Literal(act_of_association_label_2)))
            graph.add((act_of_association_uri_2, ABI.unique_id, Literal(act_of_association_hash_2)))
            graph.add((act_of_association_uri_2, ABI.hasBackingDataSource, row_uri))
            graph.add((act_of_association_uri_2, BFO.BFO_0000108, Literal(file_datetime.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
            if organization_uri is not None:
                graph.add((act_of_association_uri_2, BFO.BFO_0000057, organization_uri))
            if person_uri is not None:
                graph.add((act_of_association_uri_2, BFO.BFO_0000057, person_uri))
            if time_in_company_uri is not None:
                graph.add((act_of_association_uri_2, ABI.startDate, time_in_company_uri))
            graph.add((act_of_association_uri_2, BFO.BFO_0000117, act_of_association_uri)) #has occurrent part
            graph.add((act_of_association_uri, BFO.BFO_0000132, act_of_association_uri_2)) # occurrent part of

        # Add triples to triple store
        logger.debug("Step 4: Adding triples to triple store")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        log_dir_path = os.path.join(dir_path, timestamp, parameters.sheet_name)
        excel_file_name = file_name.split(".")[0]  + "_" + parameters.sheet_name + ".xlsx"
        ttl_file_name = f"insert_{file_name.split('.')[0]}_{parameters.sheet_name}.ttl"
        if len(graph) > 0:
            # Save triples to file
            save_triples(graph, log_dir_path, ttl_file_name, copy=False)
            # Save Excel file
            save_excel(df, log_dir_path, excel_file_name, parameters.sheet_name, copy=False)
            # Save graph to triple store
            self.__configuration.triple_store.insert(graph)
        return graph
    

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="linkedin_sales_navigator_import_excel",
                description="Import LinkedIn Sales Navigator data from an Excel file to the triple store",
                func=lambda **kwargs: self.run(SanaxLinkedInSalesNavigatorExtractorPipelineParameters(**kwargs)),
                args_schema=SanaxLinkedInSalesNavigatorExtractorPipelineParameters
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
