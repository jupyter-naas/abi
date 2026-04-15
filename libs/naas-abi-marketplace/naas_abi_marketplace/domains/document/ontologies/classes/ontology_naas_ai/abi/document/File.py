import hashlib
import os
from datetime import datetime
from typing import Self

from naas_abi_core.services.object_storage.ObjectStoragePort import ObjectMetaData
from naas_abi_marketplace.domains.document import ABIModule
from naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology import (
    File as _File,
)


class File(_File):
    """Action class for File"""

    def actions(self):
        """Action method - implement your logic here"""
        pass

    def read(self) -> bytes:
        module: ABIModule = ABIModule.get_instance()
        return module.engine.services.object_storage.get_object(
            prefix="", key=self.file_path
        )

    @classmethod
    def GetFromSha256(cls, sha256: str, graph_name: str) -> Self:
        module: ABIModule = ABIModule.get_instance()

        query = f"""
        PREFIX doc: <http://ontology.naas.ai/abi/document/>
        SELECT ?fileIRI WHERE {{
            GRAPH <{str(graph_name)}> {{
                ?fileIRI doc:sha256 "{sha256}" .
            }}
        }}
        """

        result = list(module.engine.services.triple_store.query(query))
        assert len(result) == 1
        return cls.from_iri(
            result[0]["fileIRI"],
            graph_name=graph_name,
            query_executor=module.engine.services.triple_store.query,
        )

    @staticmethod
    def key_from_filename(filename: str) -> str:
        return f"{filename}_{datetime.now().strftime('%Y%m%dT%H%M%S')}" + (
            f".{filename.split('.')[-1]}" if "." in filename else ""
        )

    @classmethod
    def UploadAndCreateFile(
        cls,
        content: bytes,
        filename: str,
        graph_name: str,
        destination_path: str = "",
        metadata: ObjectMetaData = None,
        kwargs: dict = {},
    ) -> Self:
        module: ABIModule = ABIModule.get_instance()

        sha256 = hashlib.sha256(content).hexdigest()

        key = cls.key_from_filename(filename)

        module.engine.services.object_storage.put_object(
            prefix=destination_path, key=key, content=content
        )

        metadata = (
            module.engine.services.object_storage.get_object_metadata(
                prefix=destination_path, key=key
            )
            if metadata is None
            else metadata
        )

        new_file = cls(
            label=metadata.file_name,
            file_path=os.path.join(destination_path, key),
            file_name=metadata.file_name,
            file_size_bytes=metadata.file_size_bytes,
            created_time=metadata.created_time,
            modified_time=metadata.modified_time,
            accessed_time=metadata.accessed_time,
            mime_type=metadata.mime_type,
            encoding=metadata.encoding,
            sha256=sha256,
            **kwargs,
        )

        module.engine.services.triple_store.insert(
            new_file.rdf(), graph_name=graph_name
        )

        return cls.GetFromSha256(sha256, graph_name)
