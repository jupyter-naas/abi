from src import services
from abi import logger
from io import BytesIO
import json
from typing import Tuple, Dict, Union
import pandas as pd
from datetime import datetime
from rdflib import Graph
import yaml

def __make_copy(dir_path: str, file_name: str, content: bytes) -> Tuple[str, str]:
    """
    Make a copy of a file in storage with timestamp in the name.
    """
    file_name = f"{datetime.now()}_{file_name}"
    services.storage_service.put_object(
        prefix=dir_path,
        key=file_name,
        content=content
    )
    return dir_path, file_name

def get_image(dir_path: str, file_name: str) -> Union[BytesIO, None]:
    """
    Get an image from storage.
    """
    try:
        return services.storage_service.get_object(dir_path, file_name)
    except Exception as e:
        logger.info(f"Error getting image from {dir_path}: {e}")
        return None

def save_image(image: BytesIO, dir_path: str, file_name: str, copy: bool = True) -> Tuple[str, str]:
    """
    Save an image to storage.
    """
    services.storage_service.put_object(
        prefix=dir_path,
        key=file_name,
        content=image
    )
    if copy:
        __make_copy(dir_path, file_name, image.getvalue())
    return dir_path, file_name

def get_yaml(dir_path: str, file_name: str) -> Dict:
    """
    Get a YAML file from storage.
    """
    try:
        file_content = services.storage_service.get_object(dir_path, file_name).decode("utf-8")
        return yaml.safe_load(file_content)
    except Exception as e:
        logger.info(f"Error getting YAML data from {dir_path}: {e}")
        return {}

def save_yaml(data: Dict, dir_path: str, file_name: str, copy: bool = True) -> Tuple[str, str]:
    """
    Save a YAML file to storage.
    """
    content = yaml.dump(data, indent=4, allow_unicode=True).encode("utf-8")
    services.storage_service.put_object(
        prefix=dir_path,
        key=file_name,
        content=content
    )
    if copy:
        __make_copy(dir_path, file_name, content)
    return dir_path, file_name


def get_csv(dir_path: str, file_name: str, sep: str = ";", encoding: str = "utf-8") -> pd.DataFrame:
    """
    Get a CSV file from storage.
    """
    try:
        file_content = services.storage_service.get_object(dir_path, file_name).decode(encoding)
        return pd.read_csv(file_content, sep=sep)
    except Exception as e:
        logger.info(f"Error getting CSV data from {dir_path}: {e}")
        return pd.DataFrame()

def save_csv(data: pd.DataFrame, dir_path: str, file_name: str, sep: str = ";", encoding: str = "utf-8", copy: bool = True) -> Tuple[str, str]:
    """
    Save a CSV file to storage.
    """
    content = data.to_csv(index=False, encoding=encoding, sep=sep).encode(encoding)
    services.storage_service.put_object(
        prefix=dir_path,
        key=file_name,
        content=content
    )
    if copy:
        __make_copy(dir_path, file_name, content)
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
    
def save_json(data: dict, dir_path: str, file_name: str, copy: bool = True, sort_keys: bool = True) -> Tuple[str, str]:
    """
    Save JSON data to storage.
    """
    content = json.dumps(data, indent=4, ensure_ascii=False, sort_keys=sort_keys).encode("utf-8")
    services.storage_service.put_object(
        prefix=dir_path,
        key=file_name,
        content=content
    )
    if copy:
        __make_copy(dir_path, file_name, json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"))
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
    turtle_content = graph.serialize(format=format).encode("utf-8")
    services.storage_service.put_object(
        prefix=dir_path,
        key=file_name,
        content=turtle_content
    )
    if copy:
        __make_copy(dir_path, file_name, turtle_content)
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