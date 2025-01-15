from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from google.oauth2 import service_account
from google.cloud import bigquery
from google.api_core import retry

LOGO_URL = "https://cdn.icon-icons.com/icons2/2699/PNG/512/google_bigquery_logo_icon_168150.png"

@dataclass
class GCPBigQueryIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for GCP BigQuery integration.
    
    Attributes:
        service_account_path (str): Path to service account JSON file
        project_id (str): GCP project ID
        location (str): BigQuery dataset location
    """
    service_account_path: str
    project_id: str
    location: str

class GCPBigQueryIntegration(Integration):
    """GCP BigQuery API integration client using service account.
    
    This integration provides methods to interact with GCP BigQuery's API endpoints.
    """

    __configuration: GCPBigQueryIntegrationConfiguration

    def __init__(self, configuration: GCPBigQueryIntegrationConfiguration):
        """Initialize BigQuery client with service account credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.__configuration.service_account_path
            )
        
            # Initialize client
            self.__client = bigquery.Client(
                credentials=credentials,
                project=self.__configuration.project_id,
                location=self.__configuration.location
            )
        except Exception as e:
            pass
            # logger.debug(f"Failed to initialize BigQuery API client: {str(e)}")

    def run_query(self, 
                 query: str,
                 params: Optional[List[Union[str, int, float]]] = None,
                 timeout: Optional[float] = None) -> List[Dict]:
        """Run a BigQuery SQL query.
        
        Args:
            query (str): SQL query string
            params (List[Union[str, int, float]], optional): Query parameters
            timeout (float, optional): Query timeout in seconds
            
        Returns:
            List[Dict]: Query results
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(None, type(p).__name__, p)
                    for p in (params or [])
                ]
            )
            
            query_job = self.__client.query(
                query,
                job_config=job_config,
                timeout=timeout
            )
            
            return [dict(row) for row in query_job]
        except Exception as e:
            raise IntegrationConnectionError(f"BigQuery operation failed: {str(e)}")

    def create_dataset(self, 
                      dataset_id: str,
                      description: Optional[str] = None,
                      labels: Optional[Dict[str, str]] = None) -> Dict:
        """Create a new BigQuery dataset.
        
        Args:
            dataset_id (str): Dataset ID
            description (str, optional): Dataset description
            labels (Dict[str, str], optional): Dataset labels
            
        Returns:
            Dict: Created dataset information
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            dataset = bigquery.Dataset(f"{self.__configuration.project_id}.{dataset_id}")
            dataset.location = self.__configuration.location
            
            if description:
                dataset.description = description
            if labels:
                dataset.labels = labels
            
            dataset = self.__client.create_dataset(dataset, timeout=30)
            
            return {
                'id': dataset.dataset_id,
                'full_id': dataset.full_dataset_id,
                'location': dataset.location,
                'created': dataset.created.isoformat(),
                'labels': dataset.labels
            }
        except Exception as e:
            raise IntegrationConnectionError(f"BigQuery operation failed: {str(e)}")

    def create_table(self,
                    dataset_id: str,
                    table_id: str,
                    schema: List[Dict[str, str]],
                    description: Optional[str] = None,
                    partition_field: Optional[str] = None,
                    cluster_fields: Optional[List[str]] = None) -> Dict:
        """Create a BigQuery table.
        
        Args:
            dataset_id (str): Dataset ID
            table_id (str): Table ID
            schema (List[Dict[str, str]]): Table schema
            description (str, optional): Table description
            partition_field (str, optional): Field to partition by
            cluster_fields (List[str], optional): Fields to cluster by
            
        Returns:
            Dict: Created table information
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            table_ref = f"{self.__configuration.project_id}.{dataset_id}.{table_id}"
            schema_fields = [
                bigquery.SchemaField(
                    field['name'],
                    field['type'],
                    mode=field.get('mode', 'NULLABLE'),
                    description=field.get('description')
                )
                for field in schema
            ]
            
            table = bigquery.Table(table_ref, schema=schema_fields)
            
            if description:
                table.description = description
            if partition_field:
                table.time_partitioning = bigquery.TimePartitioning(
                    field=partition_field
                )
            if cluster_fields:
                table.clustering_fields = cluster_fields
            
            table = self.__client.create_table(table)
            
            return {
                'id': table.table_id,
                'full_id': table.full_table_id,
                'created': table.created.isoformat(),
                'num_rows': table.num_rows,
                'size_bytes': table.num_bytes,
                'schema': [
                    {
                        'name': field.name,
                        'type': field.field_type,
                        'mode': field.mode,
                        'description': field.description
                    }
                    for field in table.schema
                ]
            }
        except Exception as e:
            raise IntegrationConnectionError(f"BigQuery operation failed: {str(e)}")

    def load_table_from_json(self,
                           dataset_id: str,
                           table_id: str,
                           json_rows: List[Dict],
                           schema: Optional[List[Dict[str, str]]] = None) -> Dict:
        """Load data into a BigQuery table from JSON.
        
        Args:
            dataset_id (str): Dataset ID
            table_id (str): Table ID
            json_rows (List[Dict]): Data to load
            schema (List[Dict[str, str]], optional): Table schema if creating new table
            
        Returns:
            Dict: Load job information
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            table_ref = f"{self.__configuration.project_id}.{dataset_id}.{table_id}"
            job_config = bigquery.LoadJobConfig()
            job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
            
            if schema:
                job_config.schema = [
                    bigquery.SchemaField(
                        field['name'],
                        field['type'],
                        mode=field.get('mode', 'NULLABLE'),
                        description=field.get('description')
                    )
                    for field in schema
                ]
                job_config.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE
            else:
                job_config.autodetect = True
                job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
            
            load_job = self.__client.load_table_from_json(
                json_rows,
                table_ref,
                job_config=job_config
            )
            
            load_job.result()  # Wait for job to complete
            
            return {
                'job_id': load_job.job_id,
                'state': load_job.state,
                'created': load_job.created.isoformat(),
                'errors': [str(e) for e in (load_job.errors or [])]
            }
        except Exception as e:
            raise IntegrationConnectionError(f"BigQuery operation failed: {str(e)}")

def as_tools(configuration: GCPBigQueryIntegrationConfiguration):
    """Convert GCP BigQuery integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = GCPBigQueryIntegration(configuration)
    
    class QuerySchema(BaseModel):
        query: str = Field(..., description="SQL query string")
        params: Optional[List[Union[str, int, float]]] = Field(None, description="Query parameters")
        timeout: Optional[float] = Field(None, description="Query timeout in seconds")

    class CreateDatasetSchema(BaseModel):
        dataset_id: str = Field(..., description="Dataset ID")
        description: Optional[str] = Field(None, description="Dataset description")
        labels: Optional[Dict[str, str]] = Field(None, description="Dataset labels")

    class CreateTableSchema(BaseModel):
        dataset_id: str = Field(..., description="Dataset ID")
        table_id: str = Field(..., description="Table ID")
        table_schema: List[Dict[str, str]] = Field(..., description="Table schema")
        description: Optional[str] = Field(None, description="Table description")
        partition_field: Optional[str] = Field(None, description="Field to partition by")
        cluster_fields: Optional[List[str]] = Field(None, description="Fields to cluster by")

    class LoadTableSchema(BaseModel):
        dataset_id: str = Field(..., description="Dataset ID")
        table_id: str = Field(..., description="Table ID")
        json_rows: List[Dict] = Field(..., description="Data to load")
        table_schema: Optional[List[Dict[str, str]]] = Field(None, description="Table schema if creating new table")
    
    return [
        StructuredTool(
            name="run_bigquery",
            description="Run a BigQuery SQL query",
            func=lambda query, params, timeout: integration.run_query(query, params, timeout),
            args_schema=QuerySchema
        ),
        StructuredTool(
            name="create_bigquery_dataset",
            description="Create a new BigQuery dataset",
            func=lambda dataset_id, description, labels:
                integration.create_dataset(dataset_id, description, labels),
            args_schema=CreateDatasetSchema
        ),
        StructuredTool(
            name="create_bigquery_table",
            description="Create a BigQuery table",
            func=lambda dataset_id, table_id, table_schema, description, partition_field, cluster_fields:
                integration.create_table(dataset_id, table_id, table_schema, description,
                                      partition_field, cluster_fields),
            args_schema=CreateTableSchema
        ),
        StructuredTool(
            name="load_bigquery_table",
            description="Load data into a BigQuery table from JSON",
            func=lambda dataset_id, table_id, json_rows, table_schema:
                integration.load_table_from_json(dataset_id, table_id, json_rows, table_schema),
            args_schema=LoadTableSchema
        )
    ] 