import io
from dataclasses import dataclass
from typing import Annotated

import pymupdf
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
class PdfToHtmlPipelineConfiguration(ConvertFileBasePipelineConfiguration):
    """Configuration for PdfToHtmlPipeline."""

    mime_type: Annotated[
        str,
        Field(description="The MIME type of the files to convert to HTML."),
    ] = "application/pdf"
    output_mime_type: Annotated[
        str,
        Field(description="The MIME type of the converted output files."),
    ] = "text/html"
    output_extension: Annotated[
        str,
        Field(description="The file extension appended to converted files."),
    ] = ".html"


class PdfToHtmlPipelineParameters(ConvertFileBasePipelineParameters):
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ] = "http://ontology.naas.ai/abi/document/PDFToHTMLProcessor"


class PdfToHtmlPipeline(ConvertFileBasePipeline):
    """Pipeline converting PDF files to HTML content while preserving layout."""

    module: ABIModule

    def __init__(self, configuration: PdfToHtmlPipelineConfiguration):
        super().__init__(configuration)
        self.module = ABIModule.get_instance()

    def convert(self, file: File) -> str:
        content = file.read()

        body_parts: list[str] = []
        with pymupdf.open(stream=io.BytesIO(content), filetype="pdf") as doc:
            for page_index, page in enumerate(doc, start=1):
                page_html = page.get_text("xhtml")
                body_parts.append(
                    f'<section class="pdf-page" data-page="{page_index}">\n{page_html}\n</section>'
                )

        body = "\n".join(body_parts)
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8" />\n'
            f"<title>{file.file_name}</title>\n"
            "</head>\n"
            f"<body>\n{body}\n</body>\n"
            "</html>\n"
        )
