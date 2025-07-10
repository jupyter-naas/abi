from abi.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
import pandas as pd
import re
from rdflib import URIRef, RDF, query
from typing import Any
from pydantic import Field
from dataclasses import dataclass
from typing import Optional, Annotated
import os
from src import config
from abi import logger
from langchain_core.tools import StructuredTool, BaseTool
from fastapi import APIRouter
from enum import Enum
from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from io import BytesIO
from datetime import datetime

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
    data_store_path: str = "storage/datastore/triplestore/export/excel"

class ExportGraphInstancesToExcelWorkflowParameters(WorkflowParameters):
    """Parameters for ExportGraphInstancesToExcel workflow."""
    excel_file_name: Annotated[Optional[str], Field(
        default="graph_instances_export.xlsx",
        description="Name of the Excel file to export.",
    )] = "graph_instances_export.xlsx"

class ExportGraphInstancesToExcelWorkflow(Workflow):
    """Workflow for exporting graph instances to Excel."""

    __configuration: ExportGraphInstancesToExcelWorkflowConfiguration

    def __init__(self, configuration: ExportGraphInstancesToExcelWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(configuration.naas_integration_config)

    def _upload_to_storage(self, excel_data: bytes, file_name: str) -> Optional[str]:
        """Upload image to Storage and return the asset URL."""
        asset = self.__naas_integration.upload_asset(
            data=excel_data,
            workspace_id=config.workspace_id,
            storage_name=config.storage_name,
            prefix=str(self.__configuration.data_store_path),
            object_name=str(file_name),
            visibility="public"
        )
        asset_url = asset.get("asset", {}).get("url")
        if not asset_url:
            logger.error(f"Error uploading image to Storage: {asset}")
            return None
        if asset_url.endswith("/"):
            asset_url = asset_url[:-1]
        return asset_url

    def export_to_excel(self, parameters: ExportGraphInstancesToExcelWorkflowParameters) -> str:
        os.makedirs(self.__configuration.data_store_path, exist_ok=True)
        graph = self.__configuration.triple_store.get()
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

        def _create_sheet_name(label: str) -> str:
            """Create sheet name: rdfs:label"""    
            # Clean the label for Excel sheet name (remove invalid characters)
            clean_label = re.sub(r'[\\/*?:"<>|]', '_', label)
            sheet_name = f"{clean_label}"
            
            # Excel sheet names are limited to 31 characters
            if len(sheet_name) > 31:
                sheet_name = sheet_name[:28] + "..."
        
            return sheet_name

        # Create Excel writer
        def autofit_columns(worksheet):
            """Autofit columns in an Excel worksheet"""
            for column in worksheet.columns:
                max_length = 0
                column = [cell for cell in column]
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except Exception as _:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

        summary_data = []
        # First collect all class info
        for row in results:
            assert isinstance(row, query.ResultRow)
            class_uri = str(row["class"])
            class_label = str(row["class_label"]).split('/')[-1] if row["class_label"] else class_uri.split('/')[-1]
            sheet_name = _create_sheet_name(class_label)
            summary_data.append({
                'URI': class_uri,
                'Type': 'Class',
                'Label': class_label,
                'Sheet Name': sheet_name
            })

        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.sort_values('Label').drop_duplicates()
        summary_df = summary_df.reset_index(drop=True)
        logger.info(f"Found {len(summary_df)} classes with individuals.")

        summary_data = []
        excel_file_path = os.path.join(self.__configuration.data_store_path, f"{datetime.now().isoformat()}_{parameters.excel_file_name}")
        with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:  # type: pd.ExcelWriter
            for _, row in summary_df.iterrows():  # type: ignore
                class_uri = str(row.get("URI", ""))  # type: ignore
                class_label = str(row.get("Label", ""))  # type: ignore
                sheet_name = str(row.get("Sheet Name", ""))  # type: ignore

                # Get all individuals of this class
                individuals: list[dict[str, Any]] = []
                total_triples: int = 0  # Add counter for actual triples
                for s in graph.subjects(RDF.type, URIRef(class_uri)):
                    individual_uri = str(s)
                    individual_data = {
                        'uri': individual_uri,
                    }
                    individual_data_properties: dict[str, Any] = { 
                        'rdfs:label': None
                    }
                    individual_object_properties: dict[str, Any] = {}
                    
                    # Count triples for this individual
                    individual_triples: int = 0

                    # Get triples for this individual
                    for s, p, o in graph.triples((URIRef(individual_uri), None, None)):
                        individual_triples += 1  # Count each triple
                        # Skip RDF/RDFS/OWL system properties and object properties
                        if str(p) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
                            continue

                        # Split on either # or /
                        if '#' in str(p):
                            prop_separator = '#'
                            prop_prefix = str(p).split(prop_separator)[0] + prop_separator
                            prop_suffix = str(p).split(prop_separator)[-1]
                        else:
                            prop_separator = '/'
                            prop_prefix = str(p).rsplit(prop_separator, 1)[0] + prop_separator
                            prop_suffix = str(p).split(prop_separator)[-1]
                        prop_label = f"{prefixes.get(prop_prefix, '')}:{prop_suffix}"

                        def add_to_dict(data: dict[str, Any], key: str, value: Any):
                            # If property already exists, convert to list
                            if key in data:
                                existing_value = data[key]
                                if isinstance(existing_value, list):
                                    existing_value.append(str(o))
                                else:
                                    # Convert existing value to list (handle None case)
                                    data[key] = [existing_value, str(o)] if existing_value is not None else [str(o)]  # type: ignore
                            else:
                                data[key] = str(o)
                            return data

                        if isinstance(o, URIRef):
                            individual_object_properties = add_to_dict(individual_object_properties, prop_label, str(o))
                        else:
                            individual_data_properties = add_to_dict(individual_data_properties, prop_label, str(o))
                            
                    individual_data.update(individual_data_properties)
                    individual_data.update(individual_object_properties)
                    
                    total_triples += individual_triples        
                    # Join any list values
                    for key, value in individual_data.items():
                        if isinstance(value, list):
                            individual_data[key] = '; '.join(value)
                    
                    individuals.append(individual_data)
                    
                # Create dataframe and write to Excel
                if individuals:
                    df = pd.DataFrame(individuals)
                    df = df.sort_values('rdfs:label', ascending=True)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    autofit_columns(writer.sheets[sheet_name])

                summary_data.append({
                    'URI': class_uri,
                    'Type': 'Class',
                    'Label': class_label,
                    'Sheet Name': f'=HYPERLINK("#\'{sheet_name}\'!A1", "{class_label}")',
                    'Number of Individuals': str(len(individuals)),
                    'Number of Triples': str((total_triples))  # Use actual triple count
                })

            # Sort and remove duplicates
            summary_df = pd.DataFrame(summary_data)
            summary_df = summary_df.sort_values('Label').drop_duplicates()
            summary_df = summary_df.reset_index(drop=True)
            summary_df = summary_df.astype({'Number of Individuals': int, 'Number of Triples': int})

            # Write summary sheet first
            writer.book.create_sheet('Summary', 0)  # Create Summary sheet in first position
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Color the sheet black
            sheet = writer.sheets['Summary']
            sheet.sheet_properties.tabColor = "000000"
            
            autofit_columns(writer.sheets['Summary'])
            # Save to BytesIO buffer and get bytes
            buffer = BytesIO()
            writer.book.save(buffer)
            excel_data = buffer.getvalue()
            buffer.close()

            # Upload to storage
            if parameters.excel_file_name is None:
                raise ValueError("Excel file name cannot be None")
            asset_url = self._upload_to_storage(excel_data, parameters.excel_file_name)
            if asset_url is None:
                raise ValueError("Failed to upload Excel file to storage.")
            
            logger.info(f"💾 Graph exported to {excel_file_path} (download URL: {asset_url})")
            return asset_url

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="export_graph_instances_to_excel",
                description="Export graph instances to Excel and return asset URL to download it.",
                func=lambda **kwargs: self.export_to_excel(ExportGraphInstancesToExcelWorkflowParameters(**kwargs)),
                args_schema=ExportGraphInstancesToExcelWorkflowParameters
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

