import json
from datetime import datetime
from io import BytesIO
from typing import Dict, Tuple

import pandas as pd
import yaml
from abi import logger
from abi.services.object_storage.ObjectStoragePort import IObjectStorageDomain
from rdflib import Graph


class StorageUtils:
    __storage_service: IObjectStorageDomain

    def __init__(self, storage_service: IObjectStorageDomain):
        self.__storage_service = storage_service

    def __make_copy(
        self, dir_path: str, file_name: str, content: bytes
    ) -> Tuple[str, str]:
        """
        Make a copy of a file in storage with timestamp in the name.
        """
        try:
            file_name = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{file_name}"
            self.__storage_service.put_object(
                prefix=dir_path, key=file_name, content=content
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error making copy in {dir_path}: {e}")
            return dir_path, file_name

    def get_text(
        self, dir_path: str, file_name: str, encoding: str = "utf-8"
    ) -> str | None:
        """
        Get a text file from storage.
        """
        try:
            content = self.__storage_service.get_object(dir_path, file_name)
            return content.decode(encoding)
        except Exception as e:
            logger.warning(f"Error getting text from {dir_path}: {e}")
            return None

    def save_text(
        self,
        text: str,
        dir_path: str,
        file_name: str,
        encoding: str = "utf-8",
        copy: bool = True,
    ) -> Tuple[str, str]:
        """
        Save a text file to storage.
        """
        try:
            content = text.encode(encoding)
            self.__storage_service.put_object(
                prefix=dir_path, key=file_name, content=content
            )
            if copy:
                self.__make_copy(dir_path, file_name, content)
            logger.debug(
                f"[save_text] File successfully written to storage: {dir_path}/{file_name}"
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error saving text to {dir_path}: {e}")
            return dir_path, file_name

    def get_image(self, dir_path: str, file_name: str) -> bytes | None:
        """
        Get an image from storage.
        """
        try:
            return self.__storage_service.get_object(dir_path, file_name)
        except Exception as e:
            logger.warning(f"Error getting image from {dir_path}: {e}")
            return None

    def save_image(
        self, image: bytes, dir_path: str, file_name: str, copy: bool = True
    ) -> Tuple[str, str]:
        """
        Save an image to storage.
        """
        try:
            self.__storage_service.put_object(
                prefix=dir_path, key=file_name, content=image
            )
            if copy:
                self.__make_copy(dir_path, file_name, image)
            logger.debug(
                f"[save_image] File successfully written to storage: {dir_path}/{file_name}"
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error saving image to {dir_path}: {e}")
            return dir_path, file_name

    def get_csv(
        self,
        dir_path: str,
        file_name: str,
        sep: str = ";",
        decimal: str = ",",
        encoding: str = "utf-8",
    ) -> pd.DataFrame:
        """
        Get a CSV file from storage.
        """
        try:
            file_content = self.__storage_service.get_object(dir_path, file_name)
            # Create a BytesIO object to avoid file name length issues
            from io import BytesIO

            csv_buffer = BytesIO(file_content)
            return pd.read_csv(csv_buffer, sep=sep, decimal=decimal, encoding=encoding)
        except Exception as e:
            logger.warning(f"Error getting CSV file from {dir_path}: {e}")
            return pd.DataFrame()

    def save_csv(
        self,
        data: pd.DataFrame,
        dir_path: str,
        file_name: str,
        sep: str = ";",
        decimal: str = ",",
        encoding: str = "utf-8",
        copy: bool = True,
    ) -> Tuple[str, str]:
        """
        Save a CSV file to storage.
        """
        try:
            self.__storage_service.put_object(
                prefix=dir_path,
                key=file_name,
                content=data.to_csv(
                    index=False, encoding=encoding, sep=sep, decimal=decimal
                ).encode(encoding),
            )
            if copy:
                self.__make_copy(
                    dir_path,
                    file_name,
                    data.to_csv(
                        index=False, encoding=encoding, sep=sep, decimal=decimal
                    ).encode(encoding),
                )
            logger.debug(
                f"[save_csv] File successfully written to storage: {dir_path}/{file_name}"
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error saving CSV file to {dir_path}: {e}")
            return dir_path, file_name

    def get_excel(
        self,
        dir_path: str,
        file_name: str,
        sheet_name: str,
        skiprows: int = 0,
        usecols: list | None = None,
    ) -> pd.DataFrame:
        """
        Get an Excel file from storage.
        """
        try:
            file_content = BytesIO(
                self.__storage_service.get_object(dir_path, file_name)
            )
            return pd.read_excel(
                file_content, sheet_name=sheet_name, skiprows=skiprows, usecols=usecols
            )
        except Exception as e:
            logger.warning(f"Error getting Excel file from {dir_path}: {e}")
            return pd.DataFrame()

    def save_excel(
        self,
        data: pd.DataFrame,
        dir_path: str,
        file_name: str,
        sheet_name: str,
        copy: bool = True,
    ) -> Tuple[str, str]:
        """
        Save an Excel file to storage.
        """
        try:
            excel_buffer = BytesIO()
            data.to_excel(excel_buffer, index=False, sheet_name=sheet_name)
            excel_buffer.seek(0)
            self.__storage_service.put_object(
                prefix=dir_path, key=file_name, content=excel_buffer.getvalue()
            )
            if copy:
                self.__make_copy(dir_path, file_name, excel_buffer.getvalue())
            logger.debug(
                f"[save_excel] File successfully written to storage: {dir_path}/{file_name}"
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error saving Excel file to {dir_path}: {e}")
            return dir_path, file_name

    def get_json(self, dir_path: str, file_name: str) -> Dict:
        """
        Get JSON data from storage.
        """
        try:
            file_content = self.__storage_service.get_object(
                dir_path, file_name
            ).decode("utf-8")
            data = json.loads(file_content)
            return data
        except Exception as e:
            logger.warning(f"Error getting JSON data from {dir_path}: {e}")
            return {}

    def save_json(
        self, data: dict | list, dir_path: str, file_name: str, copy: bool = True
    ) -> Tuple[str, str]:
        """
        Save JSON data to storage.
        """
        try:
            self.__storage_service.put_object(
                prefix=dir_path,
                key=file_name,
                content=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"),
            )
            if copy:
                # Only create a timestamped copy in storage, not local filesystem
                self.__make_copy(
                    dir_path,
                    file_name,
                    json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"),
                )
            logger.debug(
                f"[save_json] File successfully written to storage: {dir_path}/{file_name}"
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error saving JSON data to {dir_path}: {e}")
            return dir_path, file_name

    def get_yaml(self, dir_path: str, file_name: str) -> Dict:
        """
        Get YAML data from storage.
        """
        try:
            file_content = self.__storage_service.get_object(
                dir_path, file_name
            ).decode("utf-8")
            data = yaml.safe_load(file_content)
            return data if data is not None else {}
        except Exception as e:
            logger.debug(f"Error getting YAML data from {dir_path}: {e}")
            return {}

    def save_yaml(
        self, data: dict | list, dir_path: str, file_name: str, copy: bool = True
    ) -> Tuple[str, str]:
        """
        Save YAML data to storage.
        """
        try:
            self.__storage_service.put_object(
                prefix=dir_path,
                key=file_name,
                content=yaml.dump(
                    data, default_flow_style=False, allow_unicode=True, sort_keys=False
                ).encode("utf-8"),
            )
            if copy:
                self.__make_copy(
                    dir_path,
                    file_name,
                    yaml.dump(
                        data,
                        default_flow_style=False,
                        allow_unicode=True,
                        sort_keys=False,
                    ).encode("utf-8"),
                )
            logger.debug(
                f"[save_yaml] File successfully written to storage: {dir_path}/{file_name}"
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error saving YAML data to {dir_path}: {e}")
            return dir_path, file_name

    def get_triples(
        self, dir_path: str, file_name: str, format: str = "turtle"
    ) -> Graph:
        """
        Get Turtle data from storage and return as RDFlib Graph.
        """
        try:
            file_content = self.__storage_service.get_object(
                dir_path, file_name
            ).decode("utf-8")
            graph = Graph()
            graph.parse(data=file_content, format=format)
            return graph
        except Exception as e:
            logger.warning(f"Error getting triples from {dir_path}: {e}")
            return Graph()

    def save_triples(
        self,
        graph: Graph,
        dir_path: str,
        file_name: str,
        format: str = "turtle",
        copy: bool = True,
    ) -> Tuple[str, str]:
        """
        Save RDFlib Graph data to storage in Turtle format.
        """
        try:
            turtle_content = graph.serialize(format=format, sort=False)
            self.__storage_service.put_object(
                prefix=dir_path, key=file_name, content=turtle_content.encode("utf-8")
            )
            if copy:
                self.__make_copy(dir_path, file_name, turtle_content.encode("utf-8"))
            logger.debug(
                f"[save_triples] File successfully written to storage: {dir_path}/{file_name}"
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error saving triples to {dir_path}: {e}")
            return dir_path, file_name

    def get_powerpoint_presentation(self, dir_path: str, file_name: str) -> BytesIO:
        """
        Get a PowerPoint presentation from storage.

        Args:
            output_dir: The directory where the presentation is stored.
            file_name: The name of the presentation file.

        Returns:
            BytesIO: A BytesIO object containing the presentation data.
        """
        try:
            data = self.__storage_service.get_object(dir_path, file_name)
            byte_stream = BytesIO(data)
            byte_stream.seek(0)
            return byte_stream
        except Exception as e:
            logger.warning(
                f"Error getting PowerPoint presentation from {dir_path}: {e}"
            )
            return BytesIO()

    def save_powerpoint_presentation(
        self, presentation, dir_path: str, file_name: str, copy: bool = True
    ) -> Tuple[str, str]:
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
            # Create byte stream
            byte_stream = BytesIO()
            presentation.save(byte_stream)
            byte_stream.seek(0)
            self.__storage_service.put_object(
                prefix=dir_path, key=file_name, content=byte_stream.getvalue()
            )
            if copy:
                self.__make_copy(dir_path, file_name, byte_stream.getvalue())
            logger.debug(
                f"[save_powerpoint_presentation] File successfully written to storage: {dir_path}/{file_name}"
            )
            return dir_path, file_name
        except Exception as e:
            logger.error(f"Error saving PowerPoint presentation to {dir_path}: {e}")
            return dir_path, file_name
