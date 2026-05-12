import os
import tempfile
from dataclasses import dataclass
from typing import Annotated

import pymupdf4llm
from naas_abi_marketplace.domains.document import ABIModule
from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.File import (
    File,
)
from naas_abi_marketplace.domains.document.pipelines.ConvertFileBasePipeline import (
    ConvertFileBasePipeline,
    ConvertFileBasePipelineConfiguration,
    ConvertFileBasePipelineParameters,
)
from pydantic import Field


@dataclass
class PdfToMarkdownPipelineConfiguration(ConvertFileBasePipelineConfiguration):
    """Configuration for PdfToMarkdownPipeline."""

    mime_type: Annotated[
        str,
        Field(description="The MIME type of the files to convert to markdown."),
    ] = "application/pdf"
    output_mime_type: Annotated[
        str,
        Field(description="The MIME type of the converted output files."),
    ] = "text/markdown"
    output_extension: Annotated[
        str,
        Field(description="The file extension appended to converted files."),
    ] = ".md"


class PdfToMarkdownPipelineParameters(ConvertFileBasePipelineParameters):
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ] = "http://ontology.naas.ai/abi/document/PDFToMarkdownProcessor"


class PdfToMarkdownPipeline(ConvertFileBasePipeline):
    """Pipeline converting PDF files to markdown content."""

    module: ABIModule

    def __init__(self, configuration: PdfToMarkdownPipelineConfiguration):
        super().__init__(configuration)
        self.module = ABIModule.get_instance()

    def convert(self, file: File) -> str:
        content = file.read()

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(content)
        temp_file.close()

        md_content = pymupdf4llm.to_markdown(temp_file.name)

        os.unlink(temp_file.name)

        return md_content
