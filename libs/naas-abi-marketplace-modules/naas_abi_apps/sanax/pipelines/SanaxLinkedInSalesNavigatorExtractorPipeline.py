"""Import LinkedIn Sales Navigator people from a Sanax Excel export into the
knowledge graph (``pipeline.sanax_linked_in_sales_navigator_extractor_pipeline``).

Port of the in-engine pipeline: same graph (URIs, hashes, classes). The Excel
file is read from object storage only (the in-engine version also tried the
local disk, which a remote module's process does not share). Existing
identifiers are looked up with SPARQL on the engine's triple store.
"""

import asyncio
import hashlib
import io
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

import pandas as pd
from naas_abi_apps.common.graph import ABI, BFO, CCO
from naas_abi_sdk.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from pydantic import Field
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

logger = logging.getLogger(__name__)
DEFAULT_GRAPH = "http://ontology.naas.ai/graph/default"


def create_hash_from_string(input_string: str) -> str:
    """sha256 hex digest, as ``naas_abi_core.utils.String.create_hash_from_string``."""
    return hashlib.sha256(input_string.encode()).hexdigest()


LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")


@dataclass
class SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(PipelineConfiguration):
    """Configuration for LinkedInSalesNavigatorExportPipeline.

    Attributes:
        triple_store: the engine triple store service (or a fake)
        storage: the engine object storage service (or a fake)
        graph_name: named graph the people are inserted into
        data_store_path (str): Path to the leadership data store
    """

    triple_store: Any = None
    storage: Any = None
    graph_name: str = DEFAULT_GRAPH
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

    file_path: Annotated[
        str,
        Field(
            description="Path of the Excel file to process",
            json_schema_extra={
                "example": "datastore/linkedin_sales_navigator/sanax_extractor/Example.xlsx"
            },
        ),
    ]
    sheet_name: Annotated[str, Field(description="Name of the sheet to process")] = (
        "LinkedIn Sales Navigator"
    )


class SanaxLinkedInSalesNavigatorExtractorPipeline(
    Pipeline[SanaxLinkedInSalesNavigatorExtractorPipelineParameters]
):
    """Pipeline for importing data from Excel tables to the triple store."""

    def __init__(
        self, configuration: SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration
    ):
        super().__init__(configuration)
        self.__configuration = configuration

    @classmethod
    def New(cls, module: Any) -> "SanaxLinkedInSalesNavigatorExtractorPipeline":
        services = module.engine.services
        return cls(
            SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(
                triple_store=services.triple_store,
                storage=services.object_storage,
                graph_name=module.configuration.graph_name,
            )
        )

    async def _get_identifiers(
        self, property_uri: URIRef = ABI.unique_id, class_uri: URIRef | None = None
    ) -> dict[str, URIRef]:
        """As core's ``SPARQLUtils.get_identifiers``: identifier -> subject URI."""
        query = f"""
            SELECT ?s ?id
            WHERE {{
                ?s <{property_uri!s}> ?id .
                {f"?s a <{class_uri!s}> ." if class_uri else ""}
            }}
        """
        try:
            result = await self.__configuration.triple_store.query(query)
            return {str(row.id): URIRef(str(row.s)) for row in result}
        except Exception as exc:  # noqa: BLE001 - as core: an empty map
            logger.error("Error getting identifiers map: %s", exc)
            return {}

    async def _modified_time(self, dir_path: str, file_name: str) -> datetime:
        """When the file was last modified in object storage (now if unknown)."""
        try:
            metadata = await self.__configuration.storage.get_object_metadata(
                dir_path, file_name
            )
            modified = metadata.modified_time
        except Exception:  # noqa: BLE001 - metadata is optional
            modified = None
        if modified is None:
            return datetime.now(UTC)
        return modified if modified.tzinfo else modified.replace(tzinfo=UTC)

    async def _put(self, dir_path: str, file_name: str, content: bytes) -> None:
        await self.__configuration.storage.put_object(dir_path, file_name, content)

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
            if "year" in duration_tokens[i]:
                if i > 0 and duration_tokens[i - 1].isdigit():
                    years = int(duration_tokens[i - 1])
                    valid = True
            elif (
                "month" in duration_tokens[i]
                and i > 0
                and duration_tokens[i - 1].isdigit()
            ):
                months = int(duration_tokens[i - 1])
                valid = True

        # If the input is invalid, return None
        if not valid:
            logger.warning(
                f"Warning: The input '{duration_str}' is invalid. Please provide data in the format 'nn years nn months' or 'nn years' or 'nn months'."
            )
            return None

        return years * 12 + months

    def calculate_start_date(
        self, duration_str: str, start_datetime: datetime | None = None
    ) -> datetime | None:
        total_months = self._parse_time_duration(duration_str)
        if total_months is None:
            return None

        # Get the first day of the current month in UTC
        if start_datetime is None:
            start_datetime = datetime.now(UTC)
        month_start_date = start_datetime.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        # Subtract the duration in months
        start_date = pd.Timestamp(month_start_date) - pd.DateOffset(months=total_months)
        return start_date

    def generate_graph_date(
        self, date: datetime, date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ"
    ) -> tuple[URIRef, Graph]:
        """Generates a URI for a date based on the given datetime object."""
        date_str = date.strftime(date_format)
        date_epoch = int(date.timestamp() * 1000)
        date_uri = ABI[str(date_epoch)]  # Create URI using timestamp
        graph = Graph()
        graph.add((date_uri, RDF.type, OWL.NamedIndividual))
        graph.add((date_uri, RDF.type, ABI.ISO8601UTCDateTime))
        graph.add((date_uri, RDFS.label, Literal(date_str, datatype=XSD.dateTime)))
        return date_uri, graph

    async def _read_and_validate_excel(
        self, parameters: SanaxLinkedInSalesNavigatorExtractorPipelineParameters
    ) -> pd.DataFrame:
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
            "Name",
            "Job Title",
            "Company",
            "Company URL",
            "Location",
            "Time in Role",
            "Time in Company",
            "LinkedIn URL",
        ]
        file_path = self.__clean_file_path(parameters.file_path)
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        sheet_name = parameters.sheet_name

        try:
            content = await self.__configuration.storage.get_object(dir_path, file_name)
            df = await asyncio.to_thread(
                pd.read_excel, io.BytesIO(content), sheet_name=sheet_name, skiprows=0
            )
            logger.debug(f"✅ Successfully read file from storage: {file_path}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"❌ File not found in storage: {e}")
            df = pd.DataFrame()

        # Validate file is not empty
        if len(df) == 0:
            logger.error(
                f"❌ Excel file: {file_path}, sheet: {sheet_name}, rows: {len(df)}"
            )
            return pd.DataFrame()
        df = df.fillna("")  # Clean dataframe
        logger.debug(f"✅ Rows to be processed: {len(df)}")

        # Validate required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.error(
                f"❌ Missing required columns in Excel file: {missing_columns}"
            )
            return pd.DataFrame()
        logger.debug(
            f"✅ Validated {len(required_columns)} required columns in Excel file"
        )

        return df

    def __clean_file_path(self, file_path: str) -> str:
        if file_path.startswith("storage"):
            return file_path[len("storage") + 1 :]
        return file_path

    async def run(
        self, parameters: SanaxLinkedInSalesNavigatorExtractorPipelineParameters
    ) -> Graph:
        if not isinstance(
            parameters, SanaxLinkedInSalesNavigatorExtractorPipelineParameters
        ):
            raise TypeError(
                "Parameters must be of type SanaxLinkedInSalesNavigatorExtractorPipelineParameters"
            )

        # Step 1: Read Excel file
        file_path = self.__clean_file_path(parameters.file_path)
        logger.debug(
            f"Step 1: Reading Excel file '{file_path}' with sheet name '{parameters.sheet_name}'"
        )
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        df = await self._read_and_validate_excel(parameters)
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
        # (From object storage: the in-engine version stat'ed the local file.
        # The path keeps its "storage/" prefix so data source hashes match.)
        file_path = os.path.join("storage", dir_path, file_name)
        file_datetime = await self._modified_time(dir_path, file_name)
        file_timestamp = file_datetime.timestamp()
        logger.debug(f"File modified at: {file_datetime}")

        # Get unique identifiers
        unique_identifiers: dict[str, URIRef] = await self._get_identifiers()
        logger.debug(f"Unique identifiers: {len(unique_identifiers)}")

        # Create backing datasource
        class_data_source_uri = URIRef("http://ontology.naas.ai/abi/DataSource")
        data_source_hash = create_hash_from_string(
            f"{file_timestamp}_{file_path}_{parameters.sheet_name}"
        )
        data_source_uri = unique_identifiers.get(data_source_hash)
        if data_source_uri is None:
            data_source_uri = ABI[str(uuid.uuid4())]
            graph.add((data_source_uri, RDF.type, OWL.NamedIndividual))
            graph.add((data_source_uri, RDF.type, class_data_source_uri))
            graph.add((data_source_uri, ABI.filename, Literal(file_name)))
            graph.add((data_source_uri, ABI.sheet_name, Literal(parameters.sheet_name)))
            graph.add((data_source_uri, ABI.unique_id, Literal(data_source_hash)))
            graph.add(
                (
                    data_source_uri,
                    ABI.extracted_at,
                    Literal(
                        file_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                        datatype=XSD.dateTime,
                    ),
                )
            )
            graph.add((data_source_uri, ABI.source_path, Literal(file_path)))
            graph.add((data_source_uri, ABI.source_type, Literal("EXCEL_FILE")))

        # Step 3: Processing rows from Excel file
        logger.debug("Step 3: Processing rows")
        count_row: int = 0
        linkedin_profile_page_uris: dict[str, URIRef] = await self._get_identifiers(
            class_uri=LINKEDIN_PROFILE_PAGE
        )
        logger.debug(
            f"- Existing LinkedIn profile page: {len(linkedin_profile_page_uris)}"
        )
        person_uris: dict[str, URIRef] = await self._get_identifiers(
            RDFS.label, class_uri=PERSON
        )
        logger.debug(f"- Existing Person: {len(person_uris)}")
        position_uris: dict[str, URIRef] = await self._get_identifiers(
            class_uri=POSITION
        )
        logger.debug(f"- Existing Positions: {len(position_uris)}")
        organization_uris: dict[str, URIRef] = await self._get_identifiers(
            RDFS.label, class_uri=ORGANIZATION
        )
        logger.debug(f"- Existing Organization: {len(organization_uris)}")
        linkedin_company_page_uris: dict[str, URIRef] = await self._get_identifiers(
            class_uri=LINKEDIN_COMPANY_PAGE
        )
        logger.debug(
            f"- Existing LinkedIn company page: {len(linkedin_company_page_uris)}"
        )
        location_uris: dict[str, URIRef] = await self._get_identifiers(
            class_uri=LOCATION
        )
        logger.debug(f"- Existing Location: {len(location_uris)}")
        if self.__configuration.limit is not None:
            df = df[: self.__configuration.limit]

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
                graph.add(
                    (
                        row_uri,
                        RDF.type,
                        URIRef("http://ontology.naas.ai/abi/DataSourceComponent"),
                    )
                )
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
                lk_linkedin_id = lk_sales_navigator_linkedin_url.split("/lead/")[
                    1
                ].split(",")[0]
                linkedin_profile_url = f"https://www.linkedin.com/in/{lk_linkedin_id}"
            logger.debug(
                f"Step 3.2: Adding LinkedIn profile page: '{linkedin_profile_url}'"
            )
            lk_profile_hash = create_hash_from_string(lk_linkedin_id)
            linkedin_profile_page_uri = linkedin_profile_page_uris.get(lk_profile_hash)

            # Create linkedin profile page if it doesn't exist
            if linkedin_profile_page_uri is None:
                linkedin_profile_page_uri = ABI[str(uuid.uuid4())]
                linkedin_profile_page_uris[lk_profile_hash] = linkedin_profile_page_uri
                graph.add((linkedin_profile_page_uri, RDF.type, OWL.NamedIndividual))
                graph.add((linkedin_profile_page_uri, RDF.type, LINKEDIN_PROFILE_PAGE))
                graph.add(
                    (
                        linkedin_profile_page_uri,
                        RDFS.label,
                        Literal(linkedin_profile_url),
                    )
                )
                graph.add(
                    (linkedin_profile_page_uri, ABI.unique_id, Literal(lk_profile_hash))
                )
                graph.add(
                    (
                        linkedin_profile_page_uri,
                        ABI.linkedin_url,
                        Literal(linkedin_profile_url),
                    )
                )
                graph.add(
                    (
                        linkedin_profile_page_uri,
                        ABI.linkedin_id,
                        Literal(lk_linkedin_id),
                    )
                )
                graph.add(
                    (linkedin_profile_page_uri, ABI.hasBackingDataSource, row_uri)
                )
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
            location_uri = (
                location_uris.get(lk_location_hash) if location != "" else None
            )

            # Create location if it doesn't exist
            if location_uri is None:
                location_uri = ABI[str(uuid.uuid4())]
                location_uris[lk_location_hash] = location_uri
                graph.add((location_uri, RDF.type, OWL.NamedIndividual))
                graph.add((location_uri, RDF.type, LOCATION))
                graph.add((location_uri, RDFS.label, Literal(location)))
                graph.add((location_uri, ABI.unique_id, Literal(lk_location_hash)))
                graph.add((location_uri, ABI.hasBackingDataSource, row_uri))
            graph.add((location_uri, BFO.BFO_0000124, person_uri))  # location of
            graph.add((person_uri, BFO.BFO_0000171, location_uri))  # located in

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
            organization_uri = (
                organization_uris.get(organization) if organization != "" else None
            )
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
            if (
                lk_sales_navigator_company_url != ""
                and "/company/" in lk_sales_navigator_company_url
            ):
                lk_company_id = lk_sales_navigator_company_url.split("/company/")[
                    1
                ].split("?")[0]
                linkedin_company_page_url = (
                    f"https://www.linkedin.com/company/{lk_company_id}"
                )

            if lk_company_id is not None:
                logger.debug(
                    f"Step 3.7: Adding LinkedIn company page: '{linkedin_company_page_url}'"
                )
                lk_company_hash = create_hash_from_string(lk_company_id)
                linkedin_company_page_uri = linkedin_company_page_uris.get(
                    lk_company_hash
                )

                # Create linkedin company page if it doesn't exist
                if linkedin_company_page_uri is None:
                    linkedin_company_page_uri = ABI[str(uuid.uuid4())]
                    linkedin_company_page_uris[lk_company_hash] = (
                        linkedin_company_page_uri
                    )
                    graph.add(
                        (linkedin_company_page_uri, RDF.type, OWL.NamedIndividual)
                    )
                    graph.add(
                        (linkedin_company_page_uri, RDF.type, LINKEDIN_COMPANY_PAGE)
                    )
                    graph.add(
                        (
                            linkedin_company_page_uri,
                            RDFS.label,
                            Literal(linkedin_company_page_url),
                        )
                    )
                    graph.add(
                        (
                            linkedin_company_page_uri,
                            ABI.unique_id,
                            Literal(lk_company_hash),
                        )
                    )
                    graph.add(
                        (
                            linkedin_company_page_uri,
                            ABI.linkedin_url,
                            Literal(linkedin_company_page_url),
                        )
                    )
                    graph.add(
                        (
                            linkedin_company_page_uri,
                            ABI.linkedin_id,
                            Literal(lk_company_id),
                        )
                    )
                    graph.add(
                        (linkedin_company_page_uri, ABI.hasBackingDataSource, row_uri)
                    )

                    if organization_uri is not None:
                        graph.add(
                            (
                                linkedin_company_page_uri,
                                ABI.isLinkedInPageOf,
                                organization_uri,
                            )
                        )
                        graph.add(
                            (
                                organization_uri,
                                ABI.hasLinkedInPage,
                                linkedin_company_page_uri,
                            )
                        )

            # Create act of association
            time_in_role = row.get(
                "Time in Role", "0 months in role"
            )  # Get Time in Role
            time_in_company = row.get(
                "Time in Company", "0 months in company"
            )  # Get Time in Company

            # Calculate actual start dates for role and company
            time_in_role_start_date = self.calculate_start_date(
                time_in_role, file_datetime
            )
            time_in_company_start_date = self.calculate_start_date(
                time_in_company, file_datetime
            )

            # Generate time URIs for StartDate
            if time_in_role_start_date is not None:
                time_in_role_uri, graph_time_in_role = self.generate_graph_date(
                    time_in_role_start_date
                )
                graph += graph_time_in_role
            if time_in_company_start_date is not None:
                time_in_company_uri, graph_time_in_company = self.generate_graph_date(
                    time_in_company_start_date
                )
                graph += graph_time_in_company

            # Create act of association with organization and role
            act_of_association_label = (
                f"{person_name} working at {organization} as {position}"
            )
            act_of_association_hash = create_hash_from_string(act_of_association_label)
            logger.debug(
                f"Step 3.8: Adding act of association with organization and role: '{act_of_association_label}'"
            )
            act_of_association_uri = ABI[str(uuid.uuid4())]
            graph.add((act_of_association_uri, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri, RDF.type, ACT_OF_ASSOCIATION))
            graph.add(
                (act_of_association_uri, RDFS.label, Literal(act_of_association_label))
            )
            graph.add(
                (
                    act_of_association_uri,
                    ABI.unique_id,
                    Literal(act_of_association_hash),
                )
            )
            graph.add((act_of_association_uri, ABI.hasBackingDataSource, row_uri))
            graph.add(
                (
                    act_of_association_uri,
                    BFO.BFO_0000108,
                    Literal(
                        file_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                        datatype=XSD.dateTime,
                    ),
                )
            )
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
            act_of_association_hash_2 = create_hash_from_string(
                act_of_association_label_2
            )
            logger.debug(
                f"Step 3.9: Adding act of association with organization: '{act_of_association_label_2}'"
            )
            act_of_association_uri_2 = ABI[str(uuid.uuid4())]
            graph.add((act_of_association_uri_2, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri_2, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri_2, RDF.type, ACT_OF_ASSOCIATION))
            graph.add(
                (
                    act_of_association_uri_2,
                    RDFS.label,
                    Literal(act_of_association_label_2),
                )
            )
            graph.add(
                (
                    act_of_association_uri_2,
                    ABI.unique_id,
                    Literal(act_of_association_hash_2),
                )
            )
            graph.add((act_of_association_uri_2, ABI.hasBackingDataSource, row_uri))
            graph.add(
                (
                    act_of_association_uri_2,
                    BFO.BFO_0000108,
                    Literal(
                        file_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                        datatype=XSD.dateTime,
                    ),
                )
            )
            if organization_uri is not None:
                graph.add((act_of_association_uri_2, BFO.BFO_0000057, organization_uri))
            if person_uri is not None:
                graph.add((act_of_association_uri_2, BFO.BFO_0000057, person_uri))
            if time_in_company_uri is not None:
                graph.add(
                    (act_of_association_uri_2, ABI.startDate, time_in_company_uri)
                )
            graph.add(
                (act_of_association_uri_2, BFO.BFO_0000117, act_of_association_uri)
            )  # has occurrent part
            graph.add(
                (act_of_association_uri, BFO.BFO_0000132, act_of_association_uri_2)
            )  # occurrent part of

        # Add triples to triple store
        logger.debug("Step 4: Adding triples to triple store")
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        log_dir_path = os.path.join(dir_path, timestamp, parameters.sheet_name)
        excel_file_name = (
            file_name.split(".")[0] + "_" + parameters.sheet_name + ".xlsx"
        )
        ttl_file_name = f"insert_{file_name.split('.')[0]}_{parameters.sheet_name}.ttl"
        if len(graph) > 0:
            # Save triples and the processed rows next to the source file
            await self._put(
                log_dir_path,
                ttl_file_name,
                graph.serialize(format="turtle").encode("utf-8"),
            )
            excel = io.BytesIO()
            await asyncio.to_thread(
                df.to_excel, excel, index=False, sheet_name=parameters.sheet_name
            )
            await self._put(log_dir_path, excel_file_name, excel.getvalue())
            # Save graph to triple store
            await self.__configuration.triple_store.insert(
                graph, URIRef(self.__configuration.graph_name)
            )
        return graph
