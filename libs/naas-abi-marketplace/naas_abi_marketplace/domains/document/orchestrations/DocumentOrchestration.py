import re

import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.domains.document import (
    ABIModule,
    FileIngestionConfiguration,
    HtmlToVectorConfiguration,
    MarkdownToVectorConfiguration,
)

DEFAULT_GRAPH_NAME = "http://ontology.naas.ai/graph/document"

PDF_MIME_TYPE = "application/pdf"
PDF_PROCESSOR_IRI = "http://ontology.naas.ai/abi/document/PDFToMarkdownProcessor"
PDF_HTML_PROCESSOR_IRI = "http://ontology.naas.ai/abi/document/PDFToHTMLProcessor"

DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
DOCX_PROCESSOR_IRI = "http://ontology.naas.ai/abi/document/DocxToMarkdownProcessor"

PPTX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
PPTX_PROCESSOR_IRI = "http://ontology.naas.ai/abi/document/PptxToMarkdownProcessor"


def _has_unprocessed_files(mime_type: str, processor_iri: str) -> bool:
    from naas_abi_marketplace.domains.document.pipelines.common import (
        get_files_to_process,
    )

    return len(get_files_to_process(DEFAULT_GRAPH_NAME, mime_type, processor_iri)) > 0


IN_PROGRESS_RUN_STATUSES = [
    dg.DagsterRunStatus.QUEUED,
    dg.DagsterRunStatus.NOT_STARTED,
    dg.DagsterRunStatus.STARTING,
    dg.DagsterRunStatus.STARTED,
]


def _has_in_progress_run(context: dg.SensorEvaluationContext, job_name: str) -> bool:
    """Return True if a run for `job_name` is queued, starting, or running."""
    runs = context.instance.get_runs(
        filters=dg.RunsFilter(
            job_name=job_name,
            statuses=IN_PROGRESS_RUN_STATUSES,
        ),
        limit=1,
    )
    return len(runs) > 0


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
        minimum_interval_seconds=60,
    )
    def file_ingestion_sensor(context):
        from naas_abi_marketplace.domains.document.pipelines.FilesIngestion.FilesIngestionPipeline import (
            FilesIngestionPipeline,
            FilesIngestionPipelineConfiguration,
        )

        pipeline = FilesIngestionPipeline(FilesIngestionPipelineConfiguration())

        # Make sure the input/output directories exist in the object store
        # so users can see and drop files into them even before any ingestion
        # has happened.
        pipeline._ensure_prefix_marker(config.input_path)
        pipeline._ensure_prefix_marker(config.output_path)

        if _has_in_progress_run(context, graph_name):
            return dg.SkipReason(f"Job '{graph_name}' is already running.")

        object_keys = pipeline._get_files_from_path(
            config.input_path, recursive=config.recursive
        )
        if not object_keys:
            return dg.SkipReason(
                f"No files found under '{config.input_path}'."
            )
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
        minimum_interval_seconds=60,
    )
    def pdftomarkdown_sensor(context):
        if _has_in_progress_run(context, graph_name):
            return dg.SkipReason(f"Job '{graph_name}' is already running.")
        if not _has_unprocessed_files(PDF_MIME_TYPE, PDF_PROCESSOR_IRI):
            return dg.SkipReason("No unprocessed PDF files to convert.")
        return [dg.RunRequest(run_key=None)]

    return job, pdftomarkdown_sensor


def _build_pdftohtml_job_sensor() -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    @dg.op(name="pdftohtml_pipeline")
    def pdftohtml_op():
        from naas_abi_marketplace.domains.document.pipelines.PdfToHtmlPipeline import (
            PdfToHtmlPipeline,
            PdfToHtmlPipelineConfiguration,
            PdfToHtmlPipelineParameters,
        )

        module = ABIModule.get_instance()
        img_desc = getattr(
            module.configuration, "pdftohtml_image_description", None
        )

        config_kwargs: dict = {}
        if img_desc is not None:
            config_kwargs.update(
                {
                    "image_description_api_key": img_desc.api_key,
                    "image_description_base_url": img_desc.base_url,
                    "image_description_model": img_desc.model,
                    "image_description_prompt": img_desc.prompt,
                    "image_description_concurrency": img_desc.concurrency,
                    "image_description_timeout_seconds": img_desc.timeout_seconds,
                    "image_description_picture_area_threshold": (
                        img_desc.picture_area_threshold
                    ),
                }
            )

        parameters = PdfToHtmlPipelineParameters()
        pipeline = PdfToHtmlPipeline(PdfToHtmlPipelineConfiguration(**config_kwargs))
        pipeline.run(parameters)

    graph_name = "pdftohtml_graph"

    graph = dg.GraphDefinition(name=graph_name, node_defs=[pdftohtml_op])
    job = graph.to_job(name=graph_name)

    @dg.sensor(
        name="pdftohtml_sensor",
        description="Sensor to trigger pdftohtml job",
        job=job,
        minimum_interval_seconds=60,
    )
    def pdftohtml_sensor(context):
        if _has_in_progress_run(context, graph_name):
            return dg.SkipReason(f"Job '{graph_name}' is already running.")
        if not _has_unprocessed_files(PDF_MIME_TYPE, PDF_HTML_PROCESSOR_IRI):
            return dg.SkipReason("No unprocessed PDF files to convert to HTML.")
        return [dg.RunRequest(run_key=None)]

    return job, pdftohtml_sensor


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
        minimum_interval_seconds=60,
    )
    def docxtomarkdown_sensor(context):
        if _has_in_progress_run(context, graph_name):
            return dg.SkipReason(f"Job '{graph_name}' is already running.")
        if not _has_unprocessed_files(DOCX_MIME_TYPE, DOCX_PROCESSOR_IRI):
            return dg.SkipReason("No unprocessed DOCX files to convert.")
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
        minimum_interval_seconds=60,
    )
    def pptxtomarkdown_sensor(context):
        if _has_in_progress_run(context, graph_name):
            return dg.SkipReason(f"Job '{graph_name}' is already running.")
        if not _has_unprocessed_files(PPTX_MIME_TYPE, PPTX_PROCESSOR_IRI):
            return dg.SkipReason("No unprocessed PPTX files to convert.")
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
            api_key=config.api_key,
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
            + (
                f" filtered by file_path '{config.file_path}'"
                if config.file_path
                else ""
            )
        ),
        job=job,
        minimum_interval_seconds=120,
    )
    def markdowntovector_sensor(context):
        from naas_abi_marketplace.domains.document.pipelines.MarkdownToVectorPipeline import (
            MarkdownToVectorPipeline,
            MarkdownToVectorPipelineConfiguration,
        )

        if _has_in_progress_run(context, graph_name):
            return dg.SkipReason(f"Job '{graph_name}' is already running.")

        pipeline = MarkdownToVectorPipeline(
            MarkdownToVectorPipelineConfiguration(
                collection_name=config.collection_name,
                file_path=config.file_path,
                model_id=config.model_id,
                dimension=config.dimension,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                api_key=config.api_key,
            )
        )
        markdown_files = pipeline._get_files_to_process(DEFAULT_GRAPH_NAME)
        for file_info in markdown_files:
            if not pipeline._chunk_already_vectorized(
                file_info["iri"], DEFAULT_GRAPH_NAME
            ):
                return [dg.RunRequest(run_key=None)]
        return dg.SkipReason(
            f"No unvectorized markdown files for collection '{config.collection_name}'."
        )

    return job, markdowntovector_sensor


def _build_htmltovector_job_sensor(
    config: HtmlToVectorConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", config.collection_name)
    if config.file_path:
        safe_name += "_" + re.sub(r"[^a-zA-Z0-9]", "_", config.file_path)

    @dg.op(name=f"htmltovector_{safe_name}")
    def htmltovector_op():
        from naas_abi_marketplace.domains.document.pipelines.HtmlToVectorPipeline import (
            HtmlToVectorPipeline,
            HtmlToVectorPipelineConfiguration,
            HtmlToVectorPipelineParameters,
        )

        pipeline_config = HtmlToVectorPipelineConfiguration(
            collection_name=config.collection_name,
            file_path=config.file_path,
            model_id=config.model_id,
            dimension=config.dimension,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            api_key=config.api_key,
        )
        pipeline = HtmlToVectorPipeline(pipeline_config)
        pipeline.run(HtmlToVectorPipelineParameters())

    graph_name = f"htmltovector_graph_{safe_name}"
    graph = dg.GraphDefinition(name=graph_name, node_defs=[htmltovector_op])
    job = graph.to_job(name=graph_name)

    @dg.sensor(
        name=f"htmltovector_sensor_{safe_name}",
        description=(
            f"Sensor to trigger HtmlToVector pipeline for collection "
            f"'{config.collection_name}'"
            + (
                f" filtered by file_path '{config.file_path}'"
                if config.file_path
                else ""
            )
        ),
        job=job,
        minimum_interval_seconds=120,
    )
    def htmltovector_sensor(context):
        from naas_abi_marketplace.domains.document.pipelines.HtmlToVectorPipeline import (
            HtmlToVectorPipeline,
            HtmlToVectorPipelineConfiguration,
        )

        if _has_in_progress_run(context, graph_name):
            return dg.SkipReason(f"Job '{graph_name}' is already running.")

        pipeline = HtmlToVectorPipeline(
            HtmlToVectorPipelineConfiguration(
                collection_name=config.collection_name,
                file_path=config.file_path,
                model_id=config.model_id,
                dimension=config.dimension,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                api_key=config.api_key,
            )
        )
        html_files = pipeline._get_files_to_process(DEFAULT_GRAPH_NAME)
        for file_info in html_files:
            if not pipeline._chunk_already_vectorized(
                file_info["iri"], DEFAULT_GRAPH_NAME
            ):
                return [dg.RunRequest(run_key=None)]
        return dg.SkipReason(
            f"No unvectorized HTML files for collection '{config.collection_name}'."
        )

    return job, htmltovector_sensor


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

        if getattr(module.configuration, "pdftohtml_enabled", True):
            job, sensor = _build_pdftohtml_job_sensor()
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

        for htv_config in getattr(
            module.configuration, "htmltovector_pipelines", []
        ):
            job, sensor = _build_htmltovector_job_sensor(htv_config)
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
