from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import random
from datetime import timedelta
from abi import logger
from reportlab.pdfgen import canvas
import os


@dataclass
class PDFAnalyticsConfiguration(IntegrationConfiguration):
    """Configuration for PDF Analytics.

    Attributes:
        page_size (tuple): Page size (width, height) in points. Defaults to letter
        margin (float): Page margin in inches. Defaults to 1 inch
        title_font_family (str): Font family for titles. Defaults to 'Helvetica'
        title_font_size (int): Font size for titles. Defaults to 16
        body_font_family (str): Font family for body text. Defaults to 'Helvetica'
        body_font_size (int): Font size for body text. Defaults to 12
    """

    page_size: Tuple[float, float] = letter
    margin: float = 1.0
    title_font_family: str = "Helvetica"
    title_font_size: int = 16
    body_font_family: str = "Helvetica"
    body_font_size: int = 12


class PDFAnalytics(Integration):
    """Generate PDF reports using ReportLab."""

    __configuration: PDFAnalyticsConfiguration

    def __init__(self, configuration: PDFAnalyticsConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Set up custom paragraph styles."""
        self.__styles.add(
            ParagraphStyle(
                name="CustomTitle",
                fontName=self.__configuration.title_font_family,
                fontSize=self.__configuration.title_font_size,
                spaceAfter=30,
            )
        )
        self.__styles.add(
            ParagraphStyle(
                name="CustomBody",
                fontName=self.__configuration.body_font_family,
                fontSize=self.__configuration.body_font_size,
                spaceAfter=12,
            )
        )

    def _create_document(self, filename: str) -> SimpleDocTemplate:
        """Create a PDF document with standard configuration.

        Args:
            filename (str): Name of the PDF file to create

        Returns:
            SimpleDocTemplate: Configured PDF document
        """
        return SimpleDocTemplate(
            filename,
            pagesize=self.__configuration.page_size,
            leftMargin=self.__configuration.margin * inch,
            rightMargin=self.__configuration.margin * inch,
            topMargin=self.__configuration.margin * inch,
            bottomMargin=self.__configuration.margin * inch,
        )

    def create_table_report(
        self, data: List[List[str]], headers: List[str], title: str = "Table Report"
    ) -> str:
        """Create a PDF report with a table.

        Args:
            data (List[List[str]]): Table data (rows)
            headers (List[str]): Column headers
            title (str, optional): Report title. Defaults to "Table Report"

        Returns:
            str: Path to the generated PDF file
        """
        filename = f"src/data/analytics/{title.replace(' ', '_').lower()}.pdf"
        doc = self._create_document(filename)

        elements = []

        # Add title
        elements.append(Paragraph(title, self.__styles["CustomTitle"]))
        elements.append(Spacer(1, 12))

        # Create table
        table_data = [headers] + data
        table = Table(table_data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 12),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        elements.append(table)
        doc.build(elements)

        logger.info(f"Generated table report: {filename}")
        return filename

    def create_summary_report(self, title: str, sections: Dict[str, str]) -> str:
        """Create a PDF report with text sections.

        Args:
            title (str): Report title
            sections (Dict[str, str]): Dictionary of section titles and content

        Returns:
            str: Path to the generated PDF file
        """
        filename = f"src/data/analytics/{title.replace(' ', '_').lower()}.pdf"
        doc = self._create_document(filename)

        elements = []

        # Add title
        elements.append(Paragraph(title, self.__styles["CustomTitle"]))
        elements.append(Spacer(1, 12))

        # Add sections
        for section_title, content in sections.items():
            elements.append(Paragraph(section_title, self.__styles["Heading2"]))
            elements.append(Paragraph(content, self.__styles["CustomBody"]))
            elements.append(Spacer(1, 12))

        doc.build(elements)

        logger.info(f"Generated summary report: {filename}")
        return filename

    def save_file_to_pdf(
        self, file_path: str, title: str = None, include_metadata: bool = True
    ) -> str:
        """Convert any file to PDF by including its content as text.

        Args:
            file_path (str): Path to the file to convert
            title (str, optional): Title for the PDF. Defaults to filename
            include_metadata (bool, optional): Include file metadata. Defaults to True

        Returns:
            str: Path to the generated PDF file
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        title = title or os.path.basename(file_path)
        filename = f"src/data/analytics/{title.replace(' ', '_').lower()}.pdf"
        doc = self._create_document(filename)

        elements = []

        # Add title
        elements.append(Paragraph(title, self.__styles["CustomTitle"]))

        # Add metadata if requested
        if include_metadata:
            stat = os.stat(file_path)
            metadata = {
                "File name": os.path.basename(file_path),
                "File size": f"{stat.st_size / 1024:.2f} KB",
                "Created": datetime.fromtimestamp(stat.st_ctime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "Modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }

            elements.append(Paragraph("File Information:", self.__styles["Heading2"]))
            for key, value in metadata.items():
                elements.append(
                    Paragraph(f"{key}: {value}", self.__styles["CustomBody"])
                )
            elements.append(Spacer(1, 12))

        # Add file content
        elements.append(Paragraph("File Content:", self.__styles["Heading2"]))
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                elements.append(Paragraph(content, self.__styles["CustomBody"]))
        except UnicodeDecodeError:
            elements.append(
                Paragraph(
                    "Binary file - content cannot be displayed as text",
                    self.__styles["CustomBody"],
                )
            )

        doc.build(elements)

        logger.info(f"Generated PDF from file: {filename}")
        return filename


def as_tools(configuration: PDFAnalyticsConfiguration):
    """Convert PDF Analytics into LangChain tools.

    Args:
        configuration (PDFAnalyticsConfiguration): Configuration for the reports

    Returns:
        list[StructuredTool]: List of LangChain tools for PDF report creation
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Dict, List

    class TableReportSchema(BaseModel):
        data: List[List[str]] = Field(..., description="Table data (rows)")
        headers: List[str] = Field(..., description="Column headers")
        title: str = Field(default="Table Report", description="Report title")

    class SummaryReportSchema(BaseModel):
        title: str = Field(..., description="Report title")
        sections: Dict[str, str] = Field(
            ..., description="Dictionary of section titles and content"
        )

    class FileConversionSchema(BaseModel):
        file_path: str = Field(..., description="Path to the file to convert")
        title: str = Field(None, description="Optional title for the PDF")
        include_metadata: bool = Field(
            True, description="Include file metadata in the PDF"
        )

    reports = PDFAnalytics(configuration)

    return [
        StructuredTool(
            name="create_table_report",
            description="Create a PDF report with a table",
            func=lambda **kwargs: reports.create_table_report(**kwargs),
            args_schema=TableReportSchema,
        ),
        StructuredTool(
            name="create_summary_report",
            description="Create a PDF report with text sections",
            func=lambda **kwargs: reports.create_summary_report(**kwargs),
            args_schema=SummaryReportSchema,
        ),
        StructuredTool(
            name="save_file_to_pdf",
            description="Convert any file to PDF by including its content as text",
            func=lambda **kwargs: reports.save_file_to_pdf(**kwargs),
            args_schema=FileConversionSchema,
        ),
    ]
