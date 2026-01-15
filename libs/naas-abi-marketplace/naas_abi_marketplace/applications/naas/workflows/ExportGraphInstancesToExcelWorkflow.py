import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Annotated, Any, Optional

import pandas as pd
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from naas_abi_marketplace.applications.naas import ABIModule
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from pydantic import Field
from rdflib import RDF, Graph, URIRef, query

prefixes = {
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
    "http://www.w3.org/2002/07/owl#": "owl",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
    "http://ontology.naas.ai/abi/": "abi",
    "http://purl.obolibrary.org/obo/": "bfo",
    "https://www.commoncoreontologies.org/": "cco",
    "http://www.w3.org/2001/XMLSchema#": "xsd",
    "http://www.w3.org/2004/02/skos/core#": "skos",
}


@dataclass
class ExportGraphInstancesToExcelWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ExportGraphInstancesToExcel workflow."""

    triple_store: ITripleStoreService
    naas_integration_config: NaasIntegrationConfiguration
    data_store_path: str = "datastore/triplestore/export/excel"


class ExportGraphInstancesToExcelWorkflowParameters(WorkflowParameters):
    """Parameters for ExportGraphInstancesToExcel workflow."""

    excel_file_name: Annotated[
        str,
        Field(
            description="Name of the Excel file to export.",
        ),
    ] = "graph_instances_export.xlsx"


class ExportGraphInstancesToExcelWorkflow(Workflow):
    """Workflow for exporting graph instances to Excel."""

    __configuration: ExportGraphInstancesToExcelWorkflowConfiguration

    def __init__(self, configuration: ExportGraphInstancesToExcelWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(configuration.naas_integration_config)

    def create_sheet_name(self, label: str) -> str:
        """Create sheet name: rdfs:label"""
        # Clean the label for Excel sheet name (remove invalid characters)
        clean_label = re.sub(r'[\\/*?:"<>|]', "_", label)
        sheet_name = f"{clean_label}"

        # Excel sheet names are limited to 31 characters
        if len(sheet_name) > 31:
            sheet_name = sheet_name[:28] + "..."

        return sheet_name

    def autofit_columns(
        self, writer: pd.ExcelWriter, sheet_name: str
    ) -> pd.ExcelWriter:
        """Autofit columns in an Excel worksheet"""
        worksheet = writer.sheets[sheet_name]
        label_width = 0

        # First pass to get Label column width
        for column in worksheet.columns:
            column = [cell for cell in column]
            if column[0].value == "Label":
                for cell in column:
                    try:
                        if len(str(cell.value)) > label_width:
                            label_width = len(str(cell.value))
                    except Exception as _:
                        pass
                label_width += 2
                break

        # Second pass to set all column widths
        for column in worksheet.columns:
            max_length = 0
            column = [cell for cell in column]

            # If this is Sheet Name column, use Label width
            if column[0].value == "Sheet Name":
                worksheet.column_dimensions[column[0].column_letter].width = label_width
                continue

            # Otherwise autofit based on content
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception as _:
                    pass
            adjusted_width = max_length + 2
            worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

        return writer

    def get_all_triples_by_class(self, graph: Graph) -> query.Result:
        query_sparql = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?class (COALESCE(?class_label, STR(?class)) as ?class_label)
        WHERE {
            ?individual rdf:type ?class .
            ?individual rdf:type owl:NamedIndividual .
            OPTIONAL { ?class rdfs:label ?class_label }
            FILTER(STRSTARTS(STR(?individual), "http://ontology.naas.ai/abi/"))
            FILTER(?class != owl:NamedIndividual)
        }
        ORDER BY ?class_label
        """
        results = graph.query(query_sparql)
        logger.info(f"Found {len(results)} classes.")
        return results

    def get_all_object_property_labels(self, graph: Graph) -> dict[str, str]:
        """Get object property label from URI.
        If the object property URI is not in the prefixes, return the last part of the URI."""

        sparql_query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?uri ?label
        WHERE {
            ?uri rdf:type owl:ObjectProperty ;
                 rdfs:label ?label .
        }
        """
        results = graph.query(sparql_query)
        object_property_labels: dict = {}
        for row in results:
            assert isinstance(row, query.ResultRow)
            if row[0] is not None and row[1] is not None:
                object_property_labels[str(row[0])] = str(row[1])
        logger.info(f"Found {len(object_property_labels)} object properties.")
        return object_property_labels

    def export_to_excel(
        self, parameters: ExportGraphInstancesToExcelWorkflowParameters
    ) -> Optional[str]:
        """Export graph instances to Excel and return asset URL to download it."""
        graph = self.__configuration.triple_store.get()
        all_triples = self.get_all_triples_by_class(graph)
        object_property_labels = self.get_all_object_property_labels(graph)

        # First collect all class info
        summary_data = []
        for row in all_triples:
            assert isinstance(row, query.ResultRow)
            class_uri = str(row["class"])
            class_label = (
                str(row["class_label"]).split("/")[-1]
                if row["class_label"]
                else class_uri.split("/")[-1]
            )
            sheet_name = self.create_sheet_name(class_label)
            summary_data.append(
                {
                    "URI": class_uri,
                    "Type": "Class",
                    "Label": class_label,
                    "Sheet Name": sheet_name,
                }
            )

        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.sort_values("Label").drop_duplicates()
        summary_df = summary_df.reset_index(drop=True)
        logger.info(f"Found {len(summary_df)} classes with individuals.")

        # Then collect all data properties and object properties by class
        summary_data = []
        local_dir_path = "storage/" + self.__configuration.data_store_path
        os.makedirs(local_dir_path, exist_ok=True)
        excel_file_path = os.path.join(
            local_dir_path,
            f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{parameters.excel_file_name}",
        )
        with pd.ExcelWriter(excel_file_path, engine="openpyxl") as writer:  # type: ignore
            # Collect all data properties and object properties across all classes
            all_data_properties: list[dict[str, Any]] = []
            all_object_properties: dict[str, list[dict[str, Any]]] = {}

            for _, row in summary_df.iterrows():  # type: ignore
                class_uri = str(row.get("URI", ""))  # type: ignore
                class_label = str(row.get("Label", ""))  # type: ignore
                sheet_name = str(row.get("Sheet Name", ""))  # type: ignore

                # Get all individuals of this class
                individuals: list[dict[str, Any]] = []
                total_triples: int = 0  # Add counter for actual triples

                for s in graph.subjects(RDF.type, URIRef(class_uri)):
                    individual_uri = str(s)
                    individual_data_properties: dict[str, Any] = {
                        "uri": individual_uri,
                    }

                    # Count triples for this individual
                    individual_triples: int = 2

                    # Get triples for this individual
                    for s, p, o in graph.triples((URIRef(individual_uri), None, None)):
                        individual_triples += 1  # Count each triple
                        # Skip RDF/RDFS/OWL system properties and object properties
                        if str(p) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
                            continue

                        def add_to_dict(data: dict[str, Any], key: str, value: Any):
                            # If property already exists, convert to list
                            if key in data:
                                existing_value = data[key]
                                if isinstance(existing_value, list):
                                    existing_value.append(str(o))
                                else:
                                    # Convert existing value to list (handle None case)
                                    data[key] = (
                                        [existing_value, str(o)]
                                        if existing_value is not None
                                        else [str(o)]
                                    )  # type: ignore
                            else:
                                data[key] = str(o)
                            return data

                        if isinstance(o, URIRef):
                            prop_label = object_property_labels.get(str(p), None)
                            if prop_label is None:
                                prop_label = str(p).split("/")[-1]

                            # Add to all_object_properties for separate sheet
                            if prop_label not in all_object_properties:
                                all_object_properties[prop_label] = []

                            # Get rdfs:label for subject and object
                            subject_label = None
                            object_label = None

                            # Get subject label
                            for _, label_pred, label_obj in graph.triples(
                                (
                                    URIRef(individual_uri),
                                    URIRef(
                                        "http://www.w3.org/2000/01/rdf-schema#label"
                                    ),
                                    None,
                                )
                            ):
                                subject_label = str(label_obj)
                                break

                            # Get object label
                            for _, label_pred, label_obj in graph.triples(
                                (
                                    URIRef(str(o)),
                                    URIRef(
                                        "http://www.w3.org/2000/01/rdf-schema#label"
                                    ),
                                    None,
                                )
                            ):
                                object_label = str(label_obj)
                                break

                            all_object_properties[prop_label].append(
                                {
                                    "domain_class": class_label,
                                    "domain_uri": individual_uri,
                                    "domain_label": subject_label
                                    or individual_uri.split("/")[-1],
                                    "range_uri": str(o),
                                    "range_label": object_label
                                    or str(o).split("/")[-1],
                                    "object_property_uri": str(p),
                                    "object_property_label": prop_label,
                                }
                            )
                        else:
                            # Split on either # or /
                            for k, v in prefixes.items():
                                if k in str(p):
                                    prop_suffix = str(p).split(k)[-1]
                                    prop_label = f"{v}:{prop_suffix}"
                                    break
                            else:
                                prop_label = str(p).split("/")[-1]

                            individual_data_properties = add_to_dict(
                                individual_data_properties, prop_label, str(o)
                            )

                            # Add to all_data_properties for separate sheet
                            all_data_properties.append(
                                {
                                    "uri": individual_uri,
                                    "property": prop_label,
                                    "value": str(o),
                                    "class": class_label,
                                }
                            )

                    total_triples += individual_triples

                    # Join any list values
                    for key, value in individual_data_properties.items():
                        if isinstance(value, list):
                            individual_data_properties[key] = "; ".join(value)

                    individuals.append(individual_data_properties)

                # Create dataframe and write to Excel
                if individuals:
                    df = pd.DataFrame(individuals)
                    if "rdfs:label" in df.columns:
                        df = df.sort_values("rdfs:label", ascending=True)
                    else:
                        df = df.sort_values("uri", ascending=True)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    writer = self.autofit_columns(writer, sheet_name)

                summary_data.append(
                    {
                        "URI": class_uri,
                        "Type": "Class",
                        "Label": class_label,
                        "Sheet Name": f'=HYPERLINK("#\'{sheet_name}\'!A1", "{class_label}")',
                        "Number of Individuals": str(len(individuals)),
                    }
                )

            # Create Classes summary dataframe
            summary_df = pd.DataFrame(summary_data)
            summary_df = summary_df.sort_values("Label").drop_duplicates()
            summary_df = summary_df.reset_index(drop=True)
            summary_df = summary_df.astype({"Number of Individuals": int})
            writer.book.create_sheet(
                "Classes", 0
            )  # Create Summary sheet in first position
            summary_df.to_excel(writer, sheet_name="Classes", index=False)
            sheet = writer.sheets["Classes"]
            sheet.sheet_properties.tabColor = "000000"
            writer = self.autofit_columns(writer, "Classes")

            # Create Object Properties
            object_properties_summary = []
            for prop_label, prop_data in sorted(all_object_properties.items()):
                if prop_data:
                    sheet_name = self.create_sheet_name(prop_label)
                    prop_uri = str(prop_data[0]["object_property_uri"])
                    prop_df = pd.DataFrame(prop_data)
                    prop_df = prop_df.sort_values(
                        ["domain_class", "domain_label", "range_label"]
                    )
                    prop_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    writer = self.autofit_columns(writer, sheet_name)

                    object_properties_summary.append(
                        {
                            "URI": prop_uri,
                            "Type": "Object Property",
                            "Label": prop_label,
                            "Sheet Name": f'=HYPERLINK("#\'{sheet_name}\'!A1", "{prop_label}")',
                            "Number of Relations": str(len(prop_data)),
                        }
                    )
            writer.book.create_sheet("Object Properties", 1)
            object_properties_summary_df = pd.DataFrame(object_properties_summary)
            object_properties_summary_df = object_properties_summary_df.sort_values(
                "URI"
            ).drop_duplicates()
            object_properties_summary_df = object_properties_summary_df.astype(
                {"Number of Relations": int}
            )
            object_properties_summary_df.to_excel(
                writer, sheet_name="Object Properties", index=False
            )
            sheet = writer.sheets["Object Properties"]
            sheet.sheet_properties.tabColor = "000000"
            writer = self.autofit_columns(writer, "Object Properties")

            # Save data to storage and create download URL
            buffer = BytesIO()
            writer.book.save(buffer)
            excel_data = buffer.getvalue()
            buffer.close()
            asset = self.__naas_integration.upload_asset(
                data=excel_data,
                workspace_id=ABIModule.get_instance().configuration.workspace_id,
                storage_name=ABIModule.get_instance().configuration.storage_name,
                prefix=local_dir_path,
                object_name=str(parameters.excel_file_name),
                visibility="public",
                return_url=True,
            )
            if asset is not None:
                asset_url = asset.get("asset_url")
                logger.info(
                    f"💾 Graph exported to {excel_file_path} (download URL: {asset_url})"
                )
                return asset_url
            else:
                logger.error("❌ Failed to upload asset to Naas")
                return None

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="export_graph_instances_to_excel",
                description="Export graph instances to Excel and return asset URL to download it.",
                func=lambda **kwargs: self.export_to_excel(
                    ExportGraphInstancesToExcelWorkflowParameters(**kwargs)
                ),
                args_schema=ExportGraphInstancesToExcelWorkflowParameters,
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
