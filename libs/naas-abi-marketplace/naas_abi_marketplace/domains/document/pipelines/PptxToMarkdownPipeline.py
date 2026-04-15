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

_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_NS_MAP = {"p": _P_NS, "a": _A_NS}


@dataclass
class PptxToMarkdownPipelineConfiguration(ConvertToMarkdownBasePipelineConfiguration):
    """Configuration for PptxToMarkdownPipeline."""

    mime_type: Annotated[
        str,
        Field(description="The MIME type of the files to convert to markdown."),
    ] = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class PptxToMarkdownPipelineParameters(ConvertToMarkdownBasePipelineParameters):
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ] = "http://ontology.naas.ai/abi/document/PptxToMarkdownProcessor"


class PptxToMarkdownPipeline(ConvertToMarkdownBasePipeline):
    """Pipeline converting PPTX files to markdown content."""

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return re.sub(r"[ \t]+", " ", value).strip()

    @staticmethod
    def _list_slide_paths(pptx_file: zipfile.ZipFile) -> list[str]:
        slide_paths = [
            name
            for name in pptx_file.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ]
        def _slide_index(path: str) -> int:
            match = re.search(r"slide(\d+)\.xml$", path)
            if match is None:
                return 0
            return int(match.group(1))

        slide_paths.sort(key=_slide_index)
        return slide_paths

    @classmethod
    def _extract_text_from_slide(cls, slide_xml: bytes) -> list[str]:
        root = ET.fromstring(slide_xml)
        lines: list[str] = []

        for paragraph in root.findall(".//a:p", _NS_MAP):
            parts: list[str] = []
            for node in paragraph.iter():
                if node.tag == f"{{{_A_NS}}}t" and node.text:
                    parts.append(node.text)
                elif node.tag == f"{{{_A_NS}}}br":
                    parts.append("\n")
            text = cls._normalize_whitespace("".join(parts))
            if text:
                lines.append(text)

        return lines

    def convert_to_markdown(self, file: File) -> str:
        content = file.read()
        markdown_parts: list[str] = []

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as pptx_file:
                slide_paths = self._list_slide_paths(pptx_file)
                for slide_index, slide_path in enumerate(slide_paths, start=1):
                    slide_xml = pptx_file.read(slide_path)
                    slide_lines = self._extract_text_from_slide(slide_xml)
                    if not slide_lines:
                        continue

                    markdown_parts.append(f"## Slide {slide_index}")
                    markdown_parts.extend(f"- {line}" for line in slide_lines)
        except (KeyError, zipfile.BadZipFile) as e:
            raise ValueError("Invalid PPTX content: unable to read slide XML") from e

        return "\n\n".join(markdown_parts).strip()
