import os
import re
import tempfile
from dataclasses import dataclass
from typing import Annotated

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.serializer.html import HTMLDocSerializer, HTMLParams
from docling_core.types.doc import ImageRefMode
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

_BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.DOTALL)


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
    images_scale: Annotated[
        float,
        Field(description="Resolution scale for embedded images (1.0 = native)."),
    ] = 2.0


class PdfToHtmlPipelineParameters(ConvertFileBasePipelineParameters):
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ] = "http://ontology.naas.ai/abi/document/PDFToHTMLProcessor"


class PdfToHtmlPipeline(ConvertFileBasePipeline):
    """Pipeline converting PDF files to structured HTML using docling.

    The output is a single self-contained HTML document with embedded images.
    Each PDF page is wrapped in a ``<section class="pdf-page" data-page="N">``
    block so downstream chunkers can attach page-level metadata to each chunk.
    """

    module: ABIModule
    __pipeline_options: PdfPipelineOptions

    def __init__(self, configuration: PdfToHtmlPipelineConfiguration):
        super().__init__(configuration)
        self.module = ABIModule.get_instance()
        self.__pipeline_options = PdfPipelineOptions()
        self.__pipeline_options.generate_picture_images = True
        self.__pipeline_options.images_scale = configuration.images_scale

    def _build_converter(self) -> DocumentConverter:
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self.__pipeline_options
                )
            }
        )

    def convert(self, file: File) -> str:
        content = file.read()

        # docling expects a path; write to a temp file.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = self._build_converter().convert(tmp_path)
        finally:
            os.unlink(tmp_path)

        doc = result.document
        sections: list[str] = []
        for page_no in sorted(doc.pages.keys()):
            params = HTMLParams(
                pages={page_no},
                image_mode=ImageRefMode.EMBEDDED,
            )
            page_html = HTMLDocSerializer(doc=doc, params=params).serialize().text
            match = _BODY_RE.search(page_html)
            inner = match.group(1) if match else page_html
            sections.append(
                f'<section class="pdf-page" data-page="{page_no}">\n{inner}\n</section>'
            )

        title = file.file_name
        return (
            "<!DOCTYPE html>\n"
            '<html lang="fr">\n'
            "<head>\n"
            '<meta charset="utf-8" />\n'
            f"<title>{title}</title>\n"
            "</head>\n"
            "<body>\n"
            + "\n".join(sections)
            + "\n</body>\n</html>\n"
        )
