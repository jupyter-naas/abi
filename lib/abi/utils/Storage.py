from src import services
from abi import logger
from io import BytesIO
import json
import yaml
from typing import Tuple, Dict
import pandas as pd
from datetime import datetime
from rdflib import Graph

def __make_copy(dir_path: str, file_name: str, content: bytes) -> Tuple[str, str]:
    """
    Make a copy of a file in storage with timestamp in the name.
    """
    try:
        file_name = f"{datetime.now()}_{file_name}"
        services.storage_service.put_object(
            prefix=dir_path,
            key=file_name,
            content=content
        )
        return dir_path, file_name
    except Exception as e:
        logger.info(f"Error making copy in {dir_path}: {e}")
        return dir_path, file_name

def get_excel(dir_path: str, file_name: str, sheet_name: str, skiprows: int = 0) -> pd.DataFrame:
    """
    Get an Excel file from storage.
    """
    try:
        file_content = BytesIO(services.storage_service.get_object(dir_path, file_name))
        return pd.read_excel(file_content, sheet_name=sheet_name, skiprows=skiprows)
    except Exception as e:
        logger.info(f"Error getting Excel file from {dir_path}: {e}")
        return pd.DataFrame()

def save_excel(data: pd.DataFrame, dir_path: str, file_name: str, sheet_name: str, copy: bool = True) -> Tuple[str, str]:
    """
    Save an Excel file to storage.
    """
    try:
        excel_buffer = BytesIO()
        data.to_excel(excel_buffer, index=False, sheet_name=sheet_name)
        excel_buffer.seek(0)
        services.storage_service.put_object(
            prefix=dir_path,
            key=file_name,
            content=excel_buffer.getvalue()
        )
        if copy:
            __make_copy(dir_path, file_name, excel_buffer.getvalue())
        return dir_path, file_name
    except Exception as e:
        logger.info(f"Error saving Excel file to {dir_path}: {e}")
        return dir_path, file_name
  
def get_json(dir_path: str, file_name: str) -> Dict:
    """
    Get JSON data from storage.
    """
    try:
        file_content = services.storage_service.get_object(dir_path, file_name).decode("utf-8")
        data = json.loads(file_content)
        return data
    except Exception as e:
        logger.info(f"Error getting JSON data from {dir_path}: {e}")
        return {}

def save_json(data: dict | list, dir_path: str, file_name: str, copy: bool = True) -> Tuple[str, str]:
    """
    Save JSON data to storage.
    """
    try:
        services.storage_service.put_object(
            prefix=dir_path,
            key=file_name,
            content=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8")
        )
        if copy:
            __make_copy(dir_path, file_name, json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"))
        return dir_path, file_name
    except Exception as e:
        logger.info(f"Error saving JSON data to {dir_path}: {e}")
        return dir_path, file_name

def get_yaml(dir_path: str, file_name: str) -> Dict:
    """
    Get YAML data from storage.
    """
    try:
        file_content = services.storage_service.get_object(dir_path, file_name).decode("utf-8")
        data = yaml.safe_load(file_content)
        return data if data is not None else {}
    except Exception as e:
        logger.info(f"Error getting YAML data from {dir_path}: {e}")
        return {}

def save_yaml(data: dict | list, dir_path: str, file_name: str, copy: bool = True) -> Tuple[str, str]:
    """
    Save YAML data to storage.
    """
    try:
        services.storage_service.put_object(
            prefix=dir_path,
            key=file_name,
            content=yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).encode("utf-8")
        )
        if copy:
            __make_copy(dir_path, file_name, yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).encode("utf-8"))
        return dir_path, file_name
    except Exception as e:
        logger.info(f"Error saving YAML data to {dir_path}: {e}")
        return dir_path, file_name

def get_triples(dir_path: str, file_name: str, format: str = "turtle") -> Graph:
    """
    Get Turtle data from storage and return as RDFlib Graph.
    """
    try:
        file_content = services.storage_service.get_object(dir_path, file_name).decode("utf-8")
        graph = Graph()
        graph.parse(data=file_content, format=format)
        return graph
    except Exception as e:
        logger.info(f"Error getting triples from {dir_path}: {e}")
        return Graph()

def save_triples(graph: Graph, dir_path: str, file_name: str, format: str = "turtle", copy: bool = True) -> Tuple[str, str]:
    """
    Save RDFlib Graph data to storage in Turtle format.
    """
    try:
        turtle_content = graph.serialize(format=format, sort=False)
        services.storage_service.put_object(
            prefix=dir_path,
            key=file_name,
            content=turtle_content.encode("utf-8")
        )
        if copy:
            __make_copy(dir_path, file_name, turtle_content.encode("utf-8"))
        return dir_path, file_name
    except Exception as e:
        logger.info(f"Error saving triples to {dir_path}: {e}")
        return dir_path, file_name

def get_powerpoint_presentation(dir_path: str, file_name: str) -> BytesIO:
    """
    Get a PowerPoint presentation from storage.

    Args:
        output_dir: The directory where the presentation is stored.
        file_name: The name of the presentation file.

    Returns:
        BytesIO: A BytesIO object containing the presentation data.
    """
    try:
        data = services.storage_service.get_object(dir_path, file_name)
        byte_stream = BytesIO(data)
        byte_stream.seek(0)
        return byte_stream
    except Exception as e:
        logger.info(f"Error getting PowerPoint presentation from {dir_path}: {e}")
        return BytesIO()

def save_powerpoint_presentation(presentation, dir_path: str, file_name: str, copy: bool = True) -> Tuple[str, str]:
    """
    Save a PowerPoint presentation to a file and create an asset in Naas.

    Args:
        presentation: The presentation to save.
        output_dir: The directory to save the presentation to.
        file_name: The name of the file to save the presentation to.
        naas_integration: The Naas integration to use to create the asset.

    Returns:
        str: The URL of the asset.
    """
    try:
        # Save presentation
        logger.info("-----> Saving PowerPoint presentation to Storage")
        # Create byte stream
        byte_stream = BytesIO() 
        presentation.save(byte_stream)
        byte_stream.seek(0)
        services.storage_service.put_object(
            prefix=dir_path,
            key=file_name,
            content=byte_stream.getvalue()
        )
        if copy:
            __make_copy(dir_path, file_name, byte_stream.getvalue())
        return dir_path, file_name
    except Exception as e:
        logger.info(f"Error saving PowerPoint presentation to {dir_path}: {e}")
        return dir_path, file_name