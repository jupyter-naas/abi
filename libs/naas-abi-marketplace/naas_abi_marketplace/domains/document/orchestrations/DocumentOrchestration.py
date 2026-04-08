import re

import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.domains.document import ABIModule, FileIngestionConfiguration

# File Ingestion OP
def _build_file_ingestion_job_sensor(
    config: FileIngestionConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    @dg.op(name=f"file_ingestion_{re.sub(r'[^a-zA-Z0-9]', '_', config.input_path.replace('/', '_'))}")
    def file_ingestion_op():
        from naas_abi_marketplace.domains.document.pipelines.FilesIngestion.FilesIngestionPipeline import (
            FilesIngestionPipeline, FilesIngestionPipelineConfiguration, FilesIngestionPipelineParameters        )

        parameters = FilesIngestionPipelineParameters(
            input_path=config.input_path,
            output_path=config.output_path,
            graph_name=config.graph_name,
            recursive=config.recursive,
        )
        pipeline = FilesIngestionPipeline(FilesIngestionPipelineConfiguration())
        pipeline.run(parameters)

    graph_name = f"file_ingestion_graph_{re.sub(r'[^a-zA-Z0-9]', '_', config.input_path.replace('/', '_'))}"

    graph = dg.GraphDefinition(name=graph_name, node_defs=[file_ingestion_op])
    job = graph.to_job(name=graph_name)

    @dg.sensor( 
        name=f"file_ingestion_sensor_{re.sub(r'[^a-zA-Z0-9]', '_', config.input_path.replace('/', '_'))}",
        description=f"Sensor to trigger file ingestion job for {config.input_path}",
        job=job,
        minimum_interval_seconds=60,  # Check for new files every 60 seconds
    )
    def file_ingestion_sensor(context):
        # Implement logic to check for new files in the specified location.
        # If new files are found, return a RunRequest to trigger the job.
        # For example:
        # if new_files_found(location):
        #     return [dg.RunRequest(run_key=None, run_config={})]
        return [dg.RunRequest(run_key=None)]

    return job, file_ingestion_sensor


class DocumentOrchestration(DagsterOrchestration):
    @classmethod
    def New(cls) -> "DocumentOrchestration":

        module = ABIModule.get_instance()

        file_ingestion_jobs: list[dg.JobDefinition] = []
        file_ingestion_sensors = []
        for file_ingestion_config in module.configuration.file_ingestion_pipelines:
            # For each file ingestion pipeline we need to create a sensor that will trigger a job to ingest the files.
            # The sensor will check for new files in the specified location and trigger the job if new
            # files are found.

            job, sensor = _build_file_ingestion_job_sensor(
                file_ingestion_config
            )

            file_ingestion_jobs.append(job)
            file_ingestion_sensors.append(sensor)

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=file_ingestion_jobs,
                sensors=[] + file_ingestion_sensors,
            )
        )
