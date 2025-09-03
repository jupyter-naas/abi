from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from pydantic import Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from typing import Any, Dict, List, Union
from enum import Enum
import json
from collections.abc import MutableMapping
import pydash as _


@dataclass
class LinkedInJSONCleanerWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for LinkedInJSONCleanerWorkflow.
    
    Attributes:
        flatten_result (bool): Whether to flatten the final result dictionary
        include_images (bool): Whether to include and process image URLs
    """
    flatten_result: bool = True
    include_images: bool = True


class LinkedInJSONCleanerWorkflowParameters(WorkflowParameters):
    """Parameters for LinkedInJSONCleanerWorkflow execution.
    
    Attributes:
        json_data (str): JSON data as string to be cleaned and processed
        flatten_result (bool): Whether to flatten the final result dictionary
        include_images (bool): Whether to include and process image URLs
    """
    json_data: str = Field(..., description="JSON data as string to be cleaned and processed")

class LinkedInJSONCleanerWorkflow(Workflow):
    """Workflow for cleaning and processing LinkedIn JSON data to make it LLM-friendly."""
    
    __configuration: LinkedInJSONCleanerWorkflowConfiguration
    
    def __init__(self, configuration: LinkedInJSONCleanerWorkflowConfiguration):
        self.__configuration = configuration

    def _flatten_dict(self, data: Union[Dict, Any], parent_key: str = '', sep: str = '_') -> Dict:
        """
        Flattens a nested dictionary.

        Args:
            data (dict): The dictionary to flatten.
            parent_key (str, optional): The base key for the flattened dictionary. Defaults to ''.
            sep (str, optional): The separator to use between keys. Defaults to '_'.

        Returns:
            dict: The flattened dictionary.
        """
        if isinstance(data, dict):
            items: list = []
            for k, v in data.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, MutableMapping):
                    items.extend(self._flatten_dict(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
            return dict(items)
        return data

    def _clean_dict(self, data: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
        """
        Recursively cleans a dictionary by removing keys that start with '*' or contain 'urn'.

        Args:
            data (dict or list): The dictionary or list to clean.

        Returns:
            dict or list: The cleaned dictionary or list.
        """
        if not isinstance(data, (dict, list)):
            return data
        if isinstance(data, list):
            return [val for val in (self._clean_dict(x) for x in data) if val is not None]
        return {
            k: val 
            for k, val in ((k, self._clean_dict(v)) for k, v in data.items()) 
            if val is not None and not k.startswith("*") and "urn" not in k.lower()
        }

    def _get_picture_urls(self, data: Dict, key: str) -> List[str]:
        """
        Extracts picture URLs from a nested dictionary.

        Args:
            data (dict): The dictionary containing picture data.
            key (str): The key to extract picture URLs from.

        Returns:
            list: A list of picture URLs.
        """
        urls = []
        root_url = _.get(data, f"{key}.rootUrl")
        if root_url:
            for x in _.get(data, f"{key}.artifacts", []):
                file_url = x.get("fileIdentifyingUrlPathSegment")
                if file_url:
                    profile_url = f"{root_url}{file_url}"
                    urls.append(profile_url)
        return urls

    def _parse_clean(self, data: Dict, include_images: bool = True) -> Dict:
        """
        Parses and cleans LinkedIn profile data.

        Args:
            data (dict): The raw LinkedIn profile data.
            include_images (bool): Whether to process and include image URLs.

        Returns:
            dict: The parsed and cleaned data.
        """
        results: dict = {}
        included = _.get(data, "included", [])
        if len(included) == 0:
            return results
        
        for include in included:
            _type = include.get("$type")
            if _type is None or (_type.endswith("View") or _type.endswith("Group")):
                continue
                
            if _type not in results:
                entities: list = []
                results[_type] = entities
            else:
                entities = results.get(_type, [])
                if entities is None:
                    entities = []
            
            # Add Image URL full if requested
            if include_images:
                for image in ["logo", "picture", "backgroundImage"]:
                    if image in include:
                        picture_urls = self._get_picture_urls(include, image)
                        if picture_urls:
                            include[image] = picture_urls[-1]  # Take the last (highest quality) URL
            
            # Pop useless values
            if "trackingId" in include:
                include.pop("trackingId")
            
            # Add new entities
            if include:
                entities.append(include)
                results[_type] = entities
                
        return results

    def clean_json(self, parameters: LinkedInJSONCleanerWorkflowParameters) -> Dict[str, Any]:
        """
        Execute the JSON cleaning workflow.
        
        Args:
            parameters: Workflow parameters containing JSON data and options
            
        Returns:
            Dict: Cleaned and processed data ready for LLM consumption
        """
        try:
            # Parse JSON string
            raw_data = json.loads(parameters.json_data)
            
            # Clean the data
            cleaned_data = self._clean_dict(raw_data)
            
            # Parse and extract structured data
            if isinstance(cleaned_data, dict):
                parsed_data = self._parse_clean(cleaned_data, self.__configuration.include_images)
            else:
                # If cleaned_data is not a dict, return empty structure
                parsed_data = {}
            
            # Flatten if requested
            if self.__configuration.flatten_result:
                final_data = self._flatten_dict(parsed_data)
            else:
                final_data = parsed_data
                
            return {
                "status": "success",
                "cleaned_data": final_data,
                "original_size": len(str(raw_data)),
                "cleaned_size": len(str(final_data)),
                "reduction_ratio": round((1 - len(str(final_data)) / len(str(raw_data))) * 100, 2)
            }
            
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "error": f"Invalid JSON data: {str(e)}",
                "cleaned_data": None
            }
        except Exception as e:
            return {
                "status": "error", 
                "error": f"Processing failed: {str(e)}",
                "cleaned_data": None
            }

    def as_tools(self) -> List[BaseTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="linkedin_json_cleaner",
                description="Cleans and processes LinkedIn JSON data to make it LLM-friendly by removing unnecessary fields, flattening structures, and extracting image URLs",
                func=lambda **kwargs: self.clean_json(LinkedInJSONCleanerWorkflowParameters(**kwargs)),
                args_schema=LinkedInJSONCleanerWorkflowParameters
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        pass