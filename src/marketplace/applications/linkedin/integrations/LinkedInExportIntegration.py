from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from lib.abi.integration.integration import Integration, IntegrationConfiguration
import zipfile
import pandas as pd
from pathlib import Path
import os
from datetime import datetime


@dataclass
class LinkedInExportIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for LinkedIn export integration.
    
    Attributes:
        data_store_path (str): Path to store exported data
    """
    export_file_path: str
    

class LinkedInExportIntegration(Integration):
    """LinkedIn export integration for processing LinkedIn data export ZIP files."""

    __configuration: LinkedInExportIntegrationConfiguration

    def __init__(self, configuration: LinkedInExportIntegrationConfiguration):
        """Initialize LinkedIn export integration."""
        super().__init__(configuration)
        self.__configuration = configuration

    def _extract_directory(self) -> Path:
        """Extract the directory from the ZIP file.
        
        Args:
            zip_path (Path): Path to the ZIP file
            
        Returns:
            Path: Path to the extracted directory
        """
        zip_path = Path(self.__configuration.export_file_path)
        extract_dir = zip_path.parent / zip_path.stem
        
        # Remove .zip extension if present
        if extract_dir.suffix == '.zip':
            extract_dir = extract_dir.with_suffix('')

        # Create extraction directory if it doesn't exist
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        return Path(extract_dir)

    def unzip_export(self) -> Dict[str, Any]:
        """Unzip a LinkedIn export ZIP file in the same folder.
        
        Args:
            zip_file_path (str): Path to the ZIP file to unzip
            
        Returns:
            Dict: Information about the unzipped files including:
                - extracted_path: Path where files were extracted
                - files_count: Number of files extracted
                - folders_count: Number of folders created
        """
        zip_path = Path(self.__configuration.export_file_path)
        
        if not zip_path.exists():
            raise FileNotFoundError(f"ZIP file not found: {self.__configuration.export_file_path}")
        
        if not zipfile.is_zipfile(zip_path):
            raise ValueError(f"File is not a valid ZIP file: {self.__configuration.export_file_path}")
        
        # Extract to the same folder as the ZIP file
        extract_dir = self._extract_directory()
        
        files_extracted = []
        folders_created = set()
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Extract all files
                zip_ref.extractall(extract_dir)
                
                # Count files and folders
                for member in zip_ref.namelist():
                    member_path = extract_dir / member
                    if member_path.exists():
                        if member_path.is_file():
                            files_extracted.append(str(member_path.relative_to(extract_dir)))
                        elif member_path.is_dir():
                            folders_created.add(str(member_path.relative_to(extract_dir)))
        
        except zipfile.BadZipFile:
            raise ValueError(f"Invalid ZIP file: {self.__configuration.export_file_path}")
        except Exception as e:
            raise RuntimeError(f"Error extracting ZIP file: {str(e)}")
        
        file_created_at = datetime.fromtimestamp(os.path.getctime(zip_path))
        file_modified_at = datetime.fromtimestamp(os.path.getmtime(zip_path))

        return {
            "extracted_directory": str(extract_dir),
            "files_count": len(files_extracted),
            "folders_count": len(folders_created),
            "files": files_extracted,
            "folders": list(folders_created),
            "file_created_at": file_created_at,
            "file_modified_at": file_modified_at,
        }

    def list_files_and_folders(self, recursive: bool = True) -> Dict[str, List[str]]:
        """List all files and folders in a directory.
        
        Args:
            directory_path (str): Path to the directory to list
            recursive (bool): Whether to list recursively (default: False)
            
        Returns:
            Dict: Dictionary containing:
                - files: List of file paths
                - folders: List of folder paths
                - total_files: Total number of files
                - total_folders: Total number of folders
        """
        dir_path = Path(self.unzip_export()["extracted_directory"])
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {dir_path}")
        
        files = []
        folders = []
        
        if recursive:
            # Recursive listing
            for item in dir_path.rglob('*'):
                if item.is_file():
                    files.append(str(item.relative_to(dir_path)))
                elif item.is_dir():
                    folders.append(str(item.relative_to(dir_path)))
        else:
            # Non-recursive listing
            for item in dir_path.iterdir():
                if item.is_file():
                    files.append(item.name)
                elif item.is_dir():
                    folders.append(item.name)
        
        return {
            "files": sorted(files),
            "folders": sorted(folders),
            "total_files": len(files),
            "total_folders": len(folders),
            "path": str(dir_path)
        }
    

    def list_files(self) -> List[str]:
        """List all files in a directory.
        
        Args:
            directory_path (str): Path to the directory to list files from
            recursive (bool): Whether to list recursively (default: True)
            
        Returns:
            List[str]: List of file paths relative to the directory
        """
        files = self.list_files_and_folders()["files"]
        return files
    
    def read_csv(
        self, 
        csv_file_name: str, 
        sep: str = ",", 
        encodings: List[str] = ["utf-8", "latin-1"],
        header: Optional[int] = 0,
        skiprows: Optional[int] = None,
        nrows: Optional[int] = None
    ) -> pd.DataFrame:
        """Read a CSV file and return its contents.
        
        Args:
            csv_file_name (str): Name of the CSV file
            sep (str): CSV separator (default: ",")
            encodings (List[str]): List of encodings to try (default: ["utf-8", "latin-1"])
            header (int, optional): Row to use as column names (default: 0)
            skiprows (int, optional): Number of rows to skip at the start
            nrows (int, optional): Number of rows to read (None = all)
            
        Returns:
            pd.DataFrame: DataFrame containing the CSV data
        """
        csv_path = Path(os.path.join(self.unzip_export()["extracted_directory"], csv_file_name))
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        if not csv_path.is_file():
            raise ValueError(f"Path is not a file: {csv_path}")
        
        # Detect the first row that likely contains headers:
        # If sep appears in the row, check split by sep, first item len < 100 characters.

        def detect_header_row(filepath, sep, encoding, max_header_length=25):
            with open(filepath, "r", encoding=encoding, errors="replace") as f:
                for idx, line in enumerate(f):
                    # Clean any BOM from line if present
                    if idx == 0:
                        line = line.lstrip('\ufeff')
                    if sep in line:
                        parts = line.strip().split(sep)
                        if len(parts) > 0 and len(parts[0]) < max_header_length:
                            return idx
            return 0  # fallback: header is first row

        last_err = None
        df = None
        for enc in encodings:
            try:
                header_row = detect_header_row(csv_path, sep, enc)
                skiprows_val = header_row if header is not None else None
                df = pd.read_csv(
                    csv_path,
                    sep=sep,
                    encoding=enc,
                    header=0 if header is not None else None,
                    skiprows=skiprows_val if skiprows is None else skiprows,
                    nrows=nrows
                )
                break
            except Exception as e:
                last_err = e
                continue

        if df is None:
            raise RuntimeError(f"Error reading CSV file: {str(last_err)}")

        return df


def as_tools(configuration: LinkedInExportIntegrationConfiguration):
    """Convert LinkedIn export integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Annotated

    integration = LinkedInExportIntegration(configuration)

    class EmptySchema(BaseModel):
        pass

    class ReadCsvSchema(BaseModel):
        csv_file_name: str = Field(
            ...,
            description="Name of the CSV file to read"
        )
        sep: str = Field(
            ",",
            description="CSV separator character"
        )

    return [
        StructuredTool(
            name="linkedin_export_unzip",
            description="Unzip a LinkedIn export ZIP file in the same folder as the ZIP file.",
            func=lambda: integration.unzip_export(),
            args_schema=EmptySchema
        ),
        StructuredTool(
            name="linkedin_export_list_files_and_folders",
            description="List all files and folders in a directory from the LinkedIn export.",
            func=lambda: integration.list_files_and_folders(),
            args_schema=EmptySchema
        ),
        StructuredTool(
            name="linkedin_export_list_files",
            description="List all files in a directory from the LinkedIn export.",
            func=lambda: integration.list_files(),
            args_schema=EmptySchema
        ),
        StructuredTool(
            name="linkedin_export_read_csv",
            description="Read a CSV file from the LinkedIn export and return its contents as structured data.",
            func=lambda csv_file_name, sep: integration.read_csv(csv_file_name, sep),
            args_schema=ReadCsvSchema
        ),
    ]
