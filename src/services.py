import os
from abi import logger

from abi.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
    ObjectStorageService,
)
from abi.services.triple_store.TripleStoreFactory import (
    TripleStoreFactory,
    TripleStoreService,
)


class Services:
    _instance = None

    storage_service: ObjectStorageService
    triple_store_service: TripleStoreService

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config, secret):
        self.config = config
        self.secret = secret

        # In airgap mode, force dev initialization to avoid cloud services
        ai_mode = os.getenv("AI_MODE")
        if os.environ.get("ENV") == "dev" or ai_mode == "airgap":
            self.__init_dev()
        else:
            self.__init_prod()

    def __init_dev(self):
        self.storage_service = (
            ObjectStorageFactory.ObjectStorageServiceFS__find_storage()
        )

        if os.environ.get("AI_MODE") != "airgap" and self.secret.get("USE_AWS_NEPTUNE", None) == "true":
            logger.debug("Using AWS Neptune")
            self.triple_store_service = (
                TripleStoreFactory.TripleStoreServiceAWSNeptuneSSHTunnel()
            )
        else:
            try:
                logger.debug("Using Oxigraph triple store")
                self.triple_store_service = TripleStoreFactory.TripleStoreServiceOxigraph(
                    oxigraph_url="http://localhost:7878"
                )
            except Exception as e:
                logger.error(f"Error initializing Oxigraph triple store: {e}")
                logger.debug("Using Naas triple store")
                self.triple_store_service = TripleStoreFactory.TripleStoreServiceFilesystem(
                    self.config.triple_store_path
                )

    def __init_prod(self):
        self.storage_service = ObjectStorageFactory.ObjectStorageServiceNaas(
            naas_api_key=self.secret.get("NAAS_API_KEY"),
            workspace_id=self.config.workspace_id,
            storage_name=self.config.storage_name,
        )
        # Skip AWS Neptune during testing to avoid SSH tunnel initialization
        import os
        is_testing = (
            os.getenv("PYTEST_CURRENT_TEST") is not None or 
            os.getenv("TESTING") == "true" or
            "pytest" in os.getenv("_", "")
        )
        
        if self.secret.get("USE_AWS_NEPTUNE", None) == "true" and not is_testing:
            logger.debug("Using AWS Neptune")
            self.triple_store_service = (
                TripleStoreFactory.TripleStoreServiceAWSNeptuneSSHTunnel()
            )
        else:
            if is_testing:
                logger.debug("Skipping AWS Neptune during testing - using Naas triple store")
            self.triple_store_service = TripleStoreFactory.TripleStoreServiceNaas(
                naas_api_key=self.secret.get("NAAS_API_KEY"),
                workspace_id=self.config.workspace_id,
                storage_name=self.config.storage_name,
            )


services: Services = None


def init_services(config, secret):
    global services
    services = Services(config, secret)
    return services
