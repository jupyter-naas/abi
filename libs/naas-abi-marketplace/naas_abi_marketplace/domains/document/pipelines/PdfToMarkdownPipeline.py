import os
import tempfile
from dataclasses import dataclass
from typing import Annotated

# PyMuPDF is used to convert the PDF to markdown
import pymupdf4llm
from naas_abi_marketplace.domains.document import ABIModule
from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.File import (
    File,
)
from naas_abi_marketplace.domains.document.pipelines.ConvertToMarkdownBasePipeline import (
    ConvertToMarkdownBasePipeline,
    ConvertToMarkdownBasePipelineConfiguration,
    ConvertToMarkdownBasePipelineParameters,
)
from pydantic import Field


@dataclass
class PdfToMarkdownPipelineConfiguration(ConvertToMarkdownBasePipelineConfiguration):
    """Configuration for PdfToMarkdownPipeline."""

    mime_type: Annotated[
        str,
        Field(description="The MIME type of the files to convert to markdown."),
    ] = "application/pdf"


class PdfToMarkdownPipelineParameters(ConvertToMarkdownBasePipelineParameters):
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ] = "http://ontology.naas.ai/abi/document/PDFToMarkdownProcessor"


class PdfToMarkdownPipeline(ConvertToMarkdownBasePipeline):
    """Pipeline for adding a named individual."""

    module: ABIModule

    def __init__(self, configuration: PdfToMarkdownPipelineConfiguration):
        super().__init__(configuration)
        self.module = ABIModule.get_instance()

    def convert_to_markdown(self, file: File) -> str:
        content = file.read()

        # Create a temporary file to store the content
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(content)
        temp_file.close()

        # We are going to convert the file using pymupdf4llm
        md_content = pymupdf4llm.to_markdown(temp_file.name)

        # Delete the temporary file
        os.unlink(temp_file.name)

        return md_content
