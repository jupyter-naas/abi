import boto3
import pickle
from io import BytesIO
import os
import fnmatch
import json
import yaml
import naas_python
from datetime import datetime
from unidecode import unidecode
from rdflib import Graph


class StorageManager:
    # Get graph format
    @staticmethod
    def get_graph_format(file_path):
        file_format = file_path.split(".")[-1]
        if file_path.endswith("owl"):
            file_format = "xml"
        elif file_path.endswith("ttl"):
            file_format = "turtle"
        return file_format

    def __init__(
        self,
        access_key_id,
        secret_access_key,
        session_token,
        bucket_name,
        bucket_prefix,
    ):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self.bucket_name = bucket_name
        self.bucket_prefix = bucket_prefix

        # Init client
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
        )

    # Legacy data saved in local server
    def __fix_path_prefix(self, path_prefix):
        if "/home/ftp" in path_prefix:
            try:
                datalake_dir = naas_python.secret.get("ABI_DATALAKE_DIR").value
            except Exception as e:
                datalake_dir = "/home/ftp/abi/outputs"
            path_prefix = path_prefix.replace(f"{datalake_dir}/", "")
        return path_prefix

    # Get path
    def __get_path(self, path_prefix, file_name, extension=None):
        if extension is None:
            extension = file_name.split(".")[-1]
        file_name = file_name.split(f".{extension}")[0]
        return os.path.join(
            self.bucket_prefix,
            self.__fix_path_prefix(path_prefix),
            f"{file_name}.{extension}",
        )

    # Create path
    def __create_object_paths(self, path_prefix, file_name, extension):
        file_path = self.__get_path(path_prefix, file_name, extension)
        histo_path = self.__get_path(
            path_prefix,
            f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{file_name}',
            extension,
        )
        return file_path, histo_path

    # Load pickle file
    def pload(
        self,
        path_prefix,
        file_name,
        extension="pickle",
    ):
        # Init path
        file_path = self.__get_path(path_prefix, file_name, extension)
        try:
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=file_path)
            bytestream = BytesIO(obj["Body"].read())
            return pickle.load(bytestream)
        except Exception as e:
            return None

    # Dump pickle file
    def pdump(
        self,
        path_prefix,
        object_to_dump,
        file_name,
        extension="pickle",
    ):
        # Init paths
        file_path, histo_path = self.__create_object_paths(
            path_prefix, file_name, extension
        )

        # Save pickle files
        pickle_byte_obj = BytesIO()
        pickle.dump(object_to_dump, pickle_byte_obj)
        pickle_byte_obj.seek(0)
        self.s3.put_object(Bucket=self.bucket_name, Key=file_path, Body=pickle_byte_obj)
        self.s3.put_object(
            Bucket=self.bucket_name, Key=histo_path, Body=pickle_byte_obj
        )
        return file_path.split(self.bucket_prefix + "/")[1]

    # Read JSON
    def read_json(self, path_prefix, file_name, extension="json"):
        # Init path
        file_path = self.__get_path(path_prefix, file_name, extension)
        try:
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=file_path)
            file_content = obj["Body"].read().decode("utf-8")
            return json.loads(file_content)
        except Exception as e:
            return None

    # Save JSON file
    def save_json(self, obj, path_prefix, file_name, extension="json"):
        # Init paths
        file_path, histo_path = self.__create_object_paths(
            path_prefix, file_name, extension
        )

        # Save pickle files
        json_str = json.dumps(obj)
        self.s3.put_object(Bucket=self.bucket_name, Key=file_path, Body=json_str)
        self.s3.put_object(Bucket=self.bucket_name, Key=histo_path, Body=json_str)
        return file_path.split(self.bucket_prefix + "/")[1]

    # Read Graph
    def read_graph(self, path_prefix, file_name, extension=None):
        # Init path
        file_path = self.__get_path(path_prefix, file_name, extension)

        # Get file format
        file_format = StorageManager.get_graph_format(file_path)
        try:
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=file_path)
            file_content = obj["Body"].read().decode("utf-8")
            g = Graph()
            return g.parse(data=file_content, format=file_format)
        except Exception as e:
            return None

    # Save Graph file
    def save_graph(self, g, path_prefix, file_name, extension=None):
        # Init paths
        file_path, histo_path = self.__create_object_paths(
            path_prefix, file_name, extension
        )

        # Get file format
        file_format = StorageManager.get_graph_format(file_path)

        # Save pickle files
        data = g.serialize(format=file_format).encode("utf-8")
        self.s3.put_object(Bucket=self.bucket_name, Key=file_path, Body=data)
        self.s3.put_object(Bucket=self.bucket_name, Key=histo_path, Body=data)
        return file_path.split(self.bucket_prefix + "/")[1]

    # Read YAML
    def read_yaml(self, path_prefix, file_name, extension="yaml", content=False):
        # Init path
        file_path = self.__get_path(path_prefix, file_name, extension)
        try:
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=file_path)
            file_content = obj["Body"].read().decode("utf-8")
            if content:
                return file_content
            return yaml.safe_load(file_content)
        except Exception as e:
            return None

    # Save YAML file
    def save_yaml(self, obj, path_prefix, file_name, extension="yaml"):
        # Init paths
        file_path, histo_path = self.__create_object_paths(
            path_prefix, file_name, extension
        )

        # Save pickle files
        yaml_str = yaml.dump(obj)
        self.s3.put_object(Bucket=self.bucket_name, Key=file_path, Body=yaml_str)
        self.s3.put_object(Bucket=self.bucket_name, Key=histo_path, Body=yaml_str)
        return file_path.split(self.bucket_prefix + "/")[1]

    def save_data(
        self,
        obj,
        dl_dir,
        entity_name,
        file_name,
    ):
        # Get entity code
        entity_code = unidecode(entity_name.lower().replace(" ", "_").replace(".", ""))

        # Create directory path
        dir_path = os.path.join(dl_dir, entity_code, "tables", file_name)

        # Save in pickle
        self.pdump(dir_path, obj, file_name)

    def upload_file(
        self,
        source_path,
        destination_path=None,
    ):
        file_path = self.__fix_path_prefix(source_path)
        if destination_path is not None:
            file_path = self.__fix_path_prefix(destination_path)
        self.s3.upload_file(
            source_path, self.bucket_name, os.path.join(self.bucket_prefix, file_path)
        )
        print(f"✅ Object successfully uploaded: {file_path}")
        return file_path

    def list_objects(self, path_prefix=None, path_pattern=None):
        # Init
        files = []
        dir_path = self.bucket_prefix
        pattern = "*"
        if path_prefix is not None:
            dir_path = os.path.join(
                self.bucket_prefix, self.__fix_path_prefix(path_prefix)
            )
        if path_pattern is not None:
            pattern = "".join(self.__fix_path_prefix(path_pattern))
        # Initialize the pagination variables
        is_truncated = True
        continuation_token = None

        # List objects
        while is_truncated:
            # Fetch the list of objects
            if continuation_token:
                response = self.s3.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=dir_path + "/",
                    ContinuationToken=continuation_token,
                )
            else:
                response = self.s3.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=dir_path + "/"
                )
            # Check if 'Contents' is in the response
            if "Contents" in response:
                # Iterate through the objects and print their keys
                for file in response["Contents"]:
                    file_name = file["Key"].split(self.bucket_prefix + "/")[1]
                    if file_name != "" and fnmatch.fnmatch(file_name, pattern):
                        files.append(file_name)
            # Update pagination variables
            is_truncated = response.get("IsTruncated", False)
            continuation_token = response.get("NextContinuationToken", None)
        return files

    def get_object(
        self,
        path_prefix,
        file_name,
    ):
        file_path = self.__get_path(path_prefix, file_name)
        response = self.s3.get_object(Bucket=self.bucket_name, Key=file_path)
        return response

    def put_object(self, obj, path_prefix, file_name, extension):
        file_path = self.__get_path(path_prefix, file_name, extension)
        self.s3.put_object(Bucket=self.bucket_name, Key=file_path, Body=obj)
        return file_path.split(self.bucket_prefix + "/")[1]

    def delete_object(self, file_name):
        file_path = os.path.join(self.bucket_prefix, self.__fix_path_prefix(file_name))
        self.s3.delete_object(Bucket=self.bucket_name, Key=file_path)
        print(f"✅ Object '{file_name}' successfully deleted!")
