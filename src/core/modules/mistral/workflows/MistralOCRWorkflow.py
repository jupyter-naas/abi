#!/usr/bin/env python3
"""Mistral OCR Workflow for document processing and extraction."""

import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

from lib.abi.workflow import (
    Workflow,
    WorkflowConfiguration,
    WorkflowParameters,
)
from langchain_core.tools import StructuredTool, BaseTool
from fastapi import APIRouter


@dataclass
class MistralOCRWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for Mistral OCR Workflow."""
    mistral_api_key: str = ""
    output_format: str = "markdown"  # markdown, csv, both
    batch_size: int = 10  # Number of pages to process in batch


@dataclass
class MistralOCRWorkflowParameters(WorkflowParameters):
    """Parameters for Mistral OCR Workflow."""
    file_path: str
    output_format: str = "both"  # markdown, csv, both
    extract_tables: bool = True
    extract_images: bool = True
    extract_math: bool = True
    language: str = "auto"  # auto-detect or specific language


class MistralOCRWorkflow(Workflow):
    """Mistral OCR Workflow for document processing and extraction."""

    def __init__(self, configuration: MistralOCRWorkflowConfiguration):
        super().__init__(configuration)
        self.mistral_api_key = configuration.mistral_api_key
        self.output_format = configuration.output_format
        self.batch_size = configuration.batch_size

    def process_document_ocr(
        self,
        file_path: str,
        output_format: str = "both",
        extract_tables: bool = True,
        extract_images: bool = True,
        extract_math: bool = True,
        language: str = "auto"
    ) -> Dict[str, Any]:
        """
        Process a document using Mistral OCR and generate outputs.
        
        Args:
            file_path: Path to the input document (PDF, image, etc.)
            output_format: Output format - "markdown", "csv", or "both"
            extract_tables: Whether to extract tables
            extract_images: Whether to extract images
            extract_math: Whether to extract mathematical expressions
            language: Language for processing (auto-detect or specific)
            
        Returns:
            Dictionary with processing results and output file paths
        """
        try:
            # Validate input file
            input_path = Path(file_path)
            if not input_path.exists():
                return {
                    "success": False,
                    "error": f"Input file not found: {file_path}"
                }
            
            # Create output directory (dedicated OCR folder)
            output_dir = input_path.parent / f"ocr-{input_path.stem}"
            output_dir.mkdir(exist_ok=True)  # Create the directory if it doesn't exist
            base_name = input_path.stem
            
            # Process document with Mistral OCR
            # Note: This is a placeholder - actual Mistral OCR API integration needed
            ocr_result = self._call_mistral_ocr_api(
                file_path, extract_tables, extract_images, extract_math, language
            )
            
            if not ocr_result.get("success"):
                return ocr_result
            
            # Generate outputs based on format
            outputs = {}
            
            if output_format in ["markdown", "both"]:
                md_path = output_dir / f"{base_name}_ocr.md"
                self._generate_markdown_output(ocr_result, md_path)
                outputs["markdown"] = str(md_path)
            
            if output_format in ["csv", "both"]:
                csv_path = output_dir / f"{base_name}_ocr.csv"
                self._generate_csv_output(ocr_result, csv_path)
                outputs["csv"] = str(csv_path)
            
            return {
                "success": True,
                "input_file": str(input_path),
                "outputs": outputs,
                "processing_stats": {
                    "pages_processed": ocr_result.get("pages_processed", 0),
                    "tables_extracted": ocr_result.get("tables_extracted", 0),
                    "images_extracted": ocr_result.get("images_extracted", 0),
                    "math_expressions": ocr_result.get("math_expressions", 0),
                    "processing_time": ocr_result.get("processing_time", 0)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"OCR processing failed: {str(e)}"
            }

    def _call_mistral_ocr_api(
        self, 
        file_path: str, 
        extract_tables: bool, 
        extract_images: bool, 
        extract_math: bool, 
        language: str
    ) -> Dict[str, Any]:
        """
        Call Mistral OCR API to process document.
        
        Uses the official Mistral OCR API (mistral-ocr-latest) to process documents
        and extract text, tables, images, and mathematical expressions.
        """
        try:
            import base64
            import os
            from mistralai import Mistral
            
            # Initialize Mistral client
            api_key = self.mistral_api_key or os.environ.get("MISTRAL_API_KEY")
            if not api_key:
                return {
                    "success": False,
                    "error": "Mistral API key not found. Please set MISTRAL_API_KEY environment variable."
                }
            
            client = Mistral(api_key=api_key)
            
            # Encode the PDF to base64
            def encode_pdf(pdf_path):
                """Encode the pdf to base64."""
                try:
                    with open(pdf_path, "rb") as pdf_file:
                        return base64.b64encode(pdf_file.read()).decode('utf-8')
                except FileNotFoundError:
                    raise Exception(f"The file {pdf_path} was not found.")
                except Exception as e:
                    raise Exception(f"Error encoding PDF: {e}")
            
            # Get base64 encoded PDF
            base64_pdf = encode_pdf(file_path)
            
            # Call Mistral OCR API
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{base64_pdf}"
                },
                include_image_base64=True
            )
            
            # Process the response
            extracted_content = {
                "text": "",
                "tables": [],
                "images": [],
                "math": []
            }
            
            pages_processed = 0
            tables_extracted = 0
            images_extracted = 0
            math_expressions = 0
            
            # Extract content from all pages
            for page in ocr_response.pages:
                pages_processed += 1
                
                # Extract text content
                if page.markdown:
                    extracted_content["text"] += page.markdown + "\n\n"
                
                # Extract images if present
                if hasattr(page, 'images') and page.images:
                    for img in page.images:
                        images_extracted += 1
                        extracted_content["images"].append(f"image_{images_extracted}.png")
                
                # Extract tables (look for markdown table syntax)
                import re
                table_pattern = r'\|.*\|.*\n\|.*---.*\|.*\n(\|.*\|.*\n)*'
                tables = re.findall(table_pattern, page.markdown or "")
                for table in tables:
                    tables_extracted += 1
                    # Parse table structure
                    lines = table.strip().split('\n')
                    if len(lines) >= 3:  # Header + separator + at least one row
                        headers = [h.strip() for h in lines[0].split('|')[1:-1]]
                        rows = []
                        for line in lines[2:]:  # Skip header and separator
                            row = [cell.strip() for cell in line.split('|')[1:-1]]
                            if row and any(cell for cell in row):
                                rows.append(row)
                        extracted_content["tables"].append({
                            "headers": headers,
                            "rows": rows
                        })
                
                # Extract math expressions (look for LaTeX syntax)
                math_pattern = r'\$\$([^$]+)\$\$|\$([^$]+)\$'
                math_matches = re.findall(math_pattern, page.markdown or "")
                for match in math_matches:
                    math_expr = match[0] if match[0] else match[1]
                    if math_expr:
                        math_expressions += 1
                        extracted_content["math"].append(math_expr)
            
            return {
                "success": True,
                "pages_processed": pages_processed,
                "tables_extracted": tables_extracted,
                "images_extracted": images_extracted,
                "math_expressions": math_expressions,
                "processing_time": 0,  # Will be calculated by caller
                "extracted_content": extracted_content,
                "raw_response": ocr_response
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Mistral OCR API call failed: {str(e)}"
            }

    def _generate_markdown_output(self, ocr_result: Dict[str, Any], output_path: Path):
        """Generate markdown output from OCR results."""
        content = ocr_result.get("extracted_content", {})
        
        # If we have raw response with pages, use the original markdown
        if ocr_result.get("raw_response") and ocr_result["raw_response"].pages:
            md_content = "# Document OCR Results\n\n"
            md_content += f"*Processed with Mistral OCR (mistral-ocr-latest)*\n\n"
            
            for i, page in enumerate(ocr_result["raw_response"].pages):
                md_content += f"## Page {page.index}\n\n"
                if page.markdown:
                    md_content += page.markdown + "\n\n"
                md_content += "---\n\n"
        else:
            # Fallback to structured content
            md_content = "# Document OCR Results\n\n"
            
            # Add text content
            if content.get("text"):
                md_content += "## Text Content\n\n"
                md_content += content["text"] + "\n\n"
            
            # Add tables
            if content.get("tables"):
                md_content += "## Tables\n\n"
                for i, table in enumerate(content["tables"]):
                    md_content += f"### Table {i+1}\n\n"
                    if table.get("headers"):
                        md_content += "| " + " | ".join(table["headers"]) + " |\n"
                        md_content += "| " + " | ".join(["---"] * len(table["headers"])) + " |\n"
                    for row in table.get("rows", []):
                        md_content += "| " + " | ".join(row) + " |\n"
                    md_content += "\n"
            
            # Add images
            if content.get("images"):
                md_content += "## Images\n\n"
                for img in content["images"]:
                    md_content += f"![{img}]({img})\n\n"
            
            # Add math expressions
            if content.get("math"):
                md_content += "## Mathematical Expressions\n\n"
                for expr in content["math"]:
                    md_content += f"$${expr}$$\n\n"
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

    def _generate_csv_output(self, ocr_result: Dict[str, Any], output_path: Path):
        """Generate CSV output from OCR results."""
        content = ocr_result.get("extracted_content", {})
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(["Content Type", "Content", "Page", "Position"])
            
            # Write text content
            if content.get("text"):
                writer.writerow(["text", content["text"], 1, "main"])
            
            # Write tables
            if content.get("tables"):
                for i, table in enumerate(content["tables"]):
                    for j, row in enumerate(table.get("rows", [])):
                        writer.writerow(["table_row", "|".join(row), 1, f"table_{i+1}_row_{j+1}"])
            
            # Write images
            if content.get("images"):
                for img in content["images"]:
                    writer.writerow(["image", img, 1, "embedded"])
            
            # Write math expressions
            if content.get("math"):
                for expr in content["math"]:
                    writer.writerow(["math", expr, 1, "inline"])

    def as_tools(self) -> List[BaseTool]:
        """Convert workflow to LangChain tools."""
        return [
            StructuredTool.from_function(
                func=self.process_document_ocr,
                name="mistral_ocr_process_document",
                description="Process a document using Mistral OCR and generate markdown/CSV outputs. Takes a file path and generates outputs in the same location.",
                return_direct=True
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Convert workflow to FastAPI endpoints."""
        
        @router.post("/mistral-ocr/process-document")
        async def process_document_endpoint(
            file_path: str,
            output_format: str = "both",
            extract_tables: bool = True,
            extract_images: bool = True,
            extract_math: bool = True,
            language: str = "auto"
        ):
            """Process document with Mistral OCR."""
            return self.process_document_ocr(
                file_path=file_path,
                output_format=output_format,
                extract_tables=extract_tables,
                extract_images=extract_images,
                extract_math=extract_math,
                language=language
            )


# Convenience function for creating workflow
def create_mistral_ocr_workflow(
    mistral_api_key: str = "",
    output_format: str = "both",
    batch_size: int = 10
) -> MistralOCRWorkflow:
    """Create a Mistral OCR workflow instance."""
    config = MistralOCRWorkflowConfiguration(
        mistral_api_key=mistral_api_key,
        output_format=output_format,
        batch_size=batch_size
    )
    return MistralOCRWorkflow(config)
