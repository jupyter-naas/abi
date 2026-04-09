import io
import re
import zipfile
from dataclasses import dataclass
from typing import Annotated
from xml.etree import ElementTree as ET

from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.File import (
    File,
)
from naas_abi_marketplace.domains.document.pipelines.ConvertToMarkdownBasePipeline import (
    ConvertToMarkdownBasePipeline,
    ConvertToMarkdownBasePipelineConfiguration,
    ConvertToMarkdownBasePipelineParameters,
)
from pydantic import Field

_DOCX_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_DOCX_NS_MAP = {"w": _DOCX_NS}


@dataclass
class DocxToMarkdownPipelineConfiguration(ConvertToMarkdownBasePipelineConfiguration):
    """Configuration for DocxToMarkdownPipeline."""

    mime_type: Annotated[
        str,
        Field(description="The MIME type of the files to convert to markdown."),
    ] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocxToMarkdownPipelineParameters(ConvertToMarkdownBasePipelineParameters):
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ] = "http://ontology.naas.ai/abi/document/DocxToMarkdownProcessor"


class DocxToMarkdownPipeline(ConvertToMarkdownBasePipeline):
    """Pipeline converting DOCX files to markdown content."""

    @staticmethod
    def _extract_document_root(content: bytes) -> ET.Element:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as docx_file:
                xml_content = docx_file.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile) as e:
            raise ValueError("Invalid DOCX content: missing word/document.xml") from e
        return ET.fromstring(xml_content)

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return re.sub(r"[ \t]+", " ", value).strip()

    @classmethod
    def _paragraph_to_markdown(cls, paragraph: ET.Element) -> str:
        style_elem = paragraph.find("./w:pPr/w:pStyle", _DOCX_NS_MAP)
        style = style_elem.get(f"{{{_DOCX_NS}}}val", "") if style_elem is not None else ""

        text_parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{_DOCX_NS}}}t" and node.text:
                text_parts.append(node.text)
            elif node.tag == f"{{{_DOCX_NS}}}tab":
                text_parts.append("    ")
            elif node.tag in {
                f"{{{_DOCX_NS}}}br",
                f"{{{_DOCX_NS}}}cr",
            }:
                text_parts.append("\n")

        text = cls._normalize_whitespace("".join(text_parts))
        if not text:
            return ""

        heading_match = re.match(r"Heading([1-6])$", style)
        if heading_match:
            level = int(heading_match.group(1))
            return f"{'#' * level} {text}"

        if paragraph.find("./w:pPr/w:numPr", _DOCX_NS_MAP) is not None:
            return f"- {text}"

        return text

    def convert_to_markdown(self, file: File) -> str:
        content = file.read()
        root = self._extract_document_root(content)

        markdown_lines: list[str] = []
        for paragraph in root.findall(".//w:body/w:p", _DOCX_NS_MAP):
            line = self._paragraph_to_markdown(paragraph)
            if line:
                markdown_lines.append(line)

        return "\n\n".join(markdown_lines).strip()
