from abi.services.triple_store.TripleStoreService import TripleStoreService
from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__ObjectStorage import (
    TripleStoreService__SecondaryAdaptor__NaasStorage,
)
from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
    TripleStoreService__SecondaryAdaptor__Filesystem,
)
from abi.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from abi.services.triple_store.adaptors.secondary.AWSNeptune import (
    AWSNeptuneSSHTunnel,
)
from abi.services.triple_store.adaptors.secondary.Oxigraph import (
    Oxigraph,
)

import os


class TripleStoreFactory:
    @staticmethod
    def TripleStoreServiceNaas(
        naas_api_key: str,
        workspace_id: str,
        storage_name: str,
        base_prefix: str = "ontologies",
    ) -> TripleStoreService:
        """Creates an TripleStoreService using Naas object storage.

        Args:
            naas_api_key (str): API key for Naas service
            workspace_id (str): Workspace ID for Naas storage
            storage_name (str): Name of storage to use
            base_prefix (str): Base prefix for object paths. Defaults to "ontologies"

        Returns:
            TripleStoreService: Configured ontology store service using Naas storage
        """
        object_service = ObjectStorageFactory.ObjectStorageServiceNaas(
            naas_api_key=naas_api_key,
            workspace_id=workspace_id,
            storage_name=storage_name,
            base_prefix=base_prefix,
        )
        return TripleStoreService(
            TripleStoreService__SecondaryAdaptor__NaasStorage(object_service)
        )

    @staticmethod
    def TripleStoreServiceFilesystem(path: str) -> TripleStoreService:
        return TripleStoreService(
            TripleStoreService__SecondaryAdaptor__Filesystem(path)
        )

    @staticmethod
    def TripleStoreServiceAWSNeptuneSSHTunnel(
        aws_region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        db_instance_identifier: str | None = None,
        bastion_host: str | None = None,
        bastion_port: int | None = None,
        bastion_user: str | None = None,
        bastion_private_key: str | None = None,
    ) -> TripleStoreService:
        aws_region_name = os.environ.get("AWS_REGION")
        aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        db_instance_identifier = os.environ.get("AWS_NEPTUNE_DB_INSTANCE_IDENTIFIER")
        bastion_host = os.environ.get("AWS_BASTION_HOST")
        bastion_port = int(os.environ.get("AWS_BASTION_PORT", -42))
        bastion_user = os.environ.get("AWS_BASTION_USER")
        bastion_private_key = os.environ.get("AWS_BASTION_PRIVATE_KEY")

        assert aws_region_name is not None
        assert aws_access_key_id is not None
        assert aws_secret_access_key is not None
        assert db_instance_identifier is not None
        assert bastion_host is not None
        assert bastion_port is not None and bastion_port != -42
        assert bastion_user is not None
        assert bastion_private_key is not None

        return TripleStoreService(
            AWSNeptuneSSHTunnel(
                aws_region_name=aws_region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                db_instance_identifier=db_instance_identifier,
                bastion_host=bastion_host,
                bastion_port=bastion_port,
                bastion_user=bastion_user,
                bastion_private_key=bastion_private_key,
            )
        )

    @staticmethod
    def TripleStoreServiceOxigraph(
        oxigraph_url: str | None = None,
    ) -> TripleStoreService:
        """Creates a TripleStoreService using Oxigraph.

        Args:
            oxigraph_url (str, optional): URL of the Oxigraph instance.
                Defaults to OXIGRAPH_URL env var or http://localhost:7878

        Returns:
            TripleStoreService: Configured triple store service using Oxigraph
        """
        if oxigraph_url is None:
            oxigraph_url = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
        
        return TripleStoreService(
            Oxigraph(
                oxigraph_url=oxigraph_url,
            )
        )
