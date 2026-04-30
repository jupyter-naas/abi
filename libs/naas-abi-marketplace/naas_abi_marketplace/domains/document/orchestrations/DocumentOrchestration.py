import re

import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.domains.document import (
    ABIModule,
    FileIngestionConfiguration,
    MarkdownToVectorConfiguration,
)


# File Ingestion OP
def _build_file_ingestion_job_sensor(
    config: FileIngestionConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    @dg.op(
        name=f"file_ingestion_{re.sub(r'[^a-zA-Z0-9]', '_', config.input_path.replace('/', '_'))}"
    )
    def file_ingestion_op():
        from naas_abi_marketplace.domains.document.pipelines.FilesIngestion.FilesIngestionPipeline import (
            FilesIngestionPipeline,
            FilesIngestionPipelineConfiguration,
            FilesIngestionPipelineParameters,
        )

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


def _build_pdftomarkdown_job_sensor() -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    @dg.op(name="pdftomarkdown_pipeline")
    def pdftomarkdown_op():
        from naas_abi_marketplace.domains.document.pipelines.PdfToMarkdownPipeline import (
            PdfToMarkdownPipeline,
            PdfToMarkdownPipelineConfiguration,
            PdfToMarkdownPipelineParameters,
        )

        parameters = PdfToMarkdownPipelineParameters()
        pipeline = PdfToMarkdownPipeline(PdfToMarkdownPipelineConfiguration())
        pipeline.run(parameters)

    graph_name = "pdftomarkdown_graph"

    graph = dg.GraphDefinition(name=graph_name, node_defs=[pdftomarkdown_op])
    job = graph.to_job(name=graph_name)

    @dg.sensor(
        name="pdftomarkdown_sensor",
        description="Sensor to trigger pdftomarkdown job",
        job=job,
        minimum_interval_seconds=60,  # Check for new files every 60 seconds
    )
    def pdftomarkdown_sensor(context):
        # Implement logic to check for new files in the specified location.
        # If new files are found, return a RunRequest to trigger the job.
        # For example:
        # if new_files_found(location):
        #     return [dg.RunRequest(run_key=None, run_config={})]
        return [dg.RunRequest(run_key=None)]

    return job, pdftomarkdown_sensor


def _build_docxtomarkdown_job_sensor() -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    @dg.op(name="docxtomarkdown_pipeline")
    def docxtomarkdown_op():
        from naas_abi_marketplace.domains.document.pipelines.DocxToMarkdownPipeline import (
            DocxToMarkdownPipeline,
            DocxToMarkdownPipelineConfiguration,
            DocxToMarkdownPipelineParameters,
        )

        parameters = DocxToMarkdownPipelineParameters()
        pipeline = DocxToMarkdownPipeline(DocxToMarkdownPipelineConfiguration())
        pipeline.run(parameters)

    graph_name = "docxtomarkdown_graph"

    graph = dg.GraphDefinition(name=graph_name, node_defs=[docxtomarkdown_op])
    job = graph.to_job(name=graph_name)

    @dg.sensor(
        name="docxtomarkdown_sensor",
        description="Sensor to trigger docxtomarkdown job",
        job=job,
        minimum_interval_seconds=60,  # Check for new files every 60 seconds
    )
    def docxtomarkdown_sensor(context):
        # Implement logic to check for new files in the specified location.
        # If new files are found, return a RunRequest to trigger the job.
        # For example:
        # if new_files_found(location):
        #     return [dg.RunRequest(run_key=None, run_config={})]
        return [dg.RunRequest(run_key=None)]

    return job, docxtomarkdown_sensor


def _build_pptxtomarkdown_job_sensor() -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    @dg.op(name="pptxtomarkdown_pipeline")
    def pptxtomarkdown_op():
        from naas_abi_marketplace.domains.document.pipelines.PptxToMarkdownPipeline import (
            PptxToMarkdownPipeline,
            PptxToMarkdownPipelineConfiguration,
            PptxToMarkdownPipelineParameters,
        )

        parameters = PptxToMarkdownPipelineParameters()
        pipeline = PptxToMarkdownPipeline(PptxToMarkdownPipelineConfiguration())
        pipeline.run(parameters)

    graph_name = "pptxtomarkdown_graph"

    graph = dg.GraphDefinition(name=graph_name, node_defs=[pptxtomarkdown_op])
    job = graph.to_job(name=graph_name)

    @dg.sensor(
        name="pptxtomarkdown_sensor",
        description="Sensor to trigger pptxtomarkdown job",
        job=job,
        minimum_interval_seconds=60,  # Check for new files every 60 seconds
    )
    def pptxtomarkdown_sensor(context):
        # Implement logic to check for new files in the specified location.
        # If new files are found, return a RunRequest to trigger the job.
        # For example:
        # if new_files_found(location):
        #     return [dg.RunRequest(run_key=None, run_config={})]
        return [dg.RunRequest(run_key=None)]

    return job, pptxtomarkdown_sensor


def _build_markdowntovector_job_sensor(
    config: MarkdownToVectorConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", config.collection_name)
    if config.file_path:
        safe_name += "_" + re.sub(r"[^a-zA-Z0-9]", "_", config.file_path)

    @dg.op(name=f"markdowntovector_{safe_name}")
    def markdowntovector_op():
        from naas_abi_marketplace.domains.document.pipelines.MarkdownToVectorPipeline import (
            MarkdownToVectorPipeline,
            MarkdownToVectorPipelineConfiguration,
            MarkdownToVectorPipelineParameters,
        )

        pipeline_config = MarkdownToVectorPipelineConfiguration(
            collection_name=config.collection_name,
            file_path=config.file_path,
            model_id=config.model_id,
            dimension=config.dimension,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
        pipeline = MarkdownToVectorPipeline(pipeline_config)
        pipeline.run(MarkdownToVectorPipelineParameters())

    graph_name = f"markdowntovector_graph_{safe_name}"
    graph = dg.GraphDefinition(name=graph_name, node_defs=[markdowntovector_op])
    job = graph.to_job(name=graph_name)

    @dg.sensor(
        name=f"markdowntovector_sensor_{safe_name}",
        description=(
            f"Sensor to trigger MarkdownToVector pipeline for collection "
            f"'{config.collection_name}'"
            + (f" filtered by file_path '{config.file_path}'" if config.file_path else "")
        ),
        job=job,
        minimum_interval_seconds=120,
    )
    def markdowntovector_sensor(context):
        return [dg.RunRequest(run_key=None)]

    return job, markdowntovector_sensor


class DocumentOrchestration(DagsterOrchestration):
    @classmethod
    def New(cls) -> "DocumentOrchestration":

        module = ABIModule.get_instance()

        jobs: list[dg.JobDefinition] = []
        sensors = []
        for file_ingestion_config in module.configuration.file_ingestion_pipelines:
            # For each file ingestion pipeline we need to create a sensor that will trigger a job to ingest the files.
            # The sensor will check for new files in the specified location and trigger the job if new
            # files are found.

            job, sensor = _build_file_ingestion_job_sensor(file_ingestion_config)

            jobs.append(job)
            sensors.append(sensor)

        if module.configuration.pdftomarkdown_enabled:
            job, sensor = _build_pdftomarkdown_job_sensor()
            jobs.append(job)
            sensors.append(sensor)

        if getattr(module.configuration, "docxtomarkdown_enabled", True):
            job, sensor = _build_docxtomarkdown_job_sensor()
            jobs.append(job)
            sensors.append(sensor)

        if getattr(module.configuration, "pptxtomarkdown_enabled", True):
            job, sensor = _build_pptxtomarkdown_job_sensor()
            jobs.append(job)
            sensors.append(sensor)

        for mtv_config in module.configuration.markdowntovector_pipelines:
            job, sensor = _build_markdowntovector_job_sensor(mtv_config)
            jobs.append(job)
            sensors.append(sensor)

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=jobs,
                sensors=sensors,
            )
        )
