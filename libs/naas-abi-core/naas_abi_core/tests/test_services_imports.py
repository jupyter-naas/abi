# This is used to test all imports and ensure all libraries are installed and imported correctly.


def test_imports():
    from naas_abi_core.services.agent import Agent, IntentAgent
    from naas_abi_core.services.cache import CacheFactory, CachePort, CacheService
    from naas_abi_core.services.cache.adapters.secondary import CacheFSAdapter
    from naas_abi_core.services.email import EmailFactory, EmailService, IEmailAdapter
    from naas_abi_core.services.email.adapters.secondary import SMTPAdapter
    from naas_abi_core.services.object_storage import ObjectStorageService
    from naas_abi_core.services.object_storage.adapters.secondary import (
        ObjectStorageSecondaryAdapterFS,
        ObjectStorageSecondaryAdapterNaas,
        ObjectStorageSecondaryAdapterS3,
    )
    from naas_abi_core.services.secret import Secret, SecretPorts
    from naas_abi_core.services.secret.adaptors.secondary import (
        Base64Secret,
        NaasSecret,
        dotenv_secret_secondaryadaptor,
    )
    from naas_abi_core.services.triple_store import (
        TripleStoreFactory,
        TripleStorePorts,
        TripleStoreService,
    )
    from naas_abi_core.services.triple_store.adaptors.secondary import (
        ApacheJenaTDB2,
        AWSNeptune,
        Oxigraph,
    )
    from naas_abi_core.services.vector_store import (
        IVectorStorePort,
        VectorStoreFactory,
        VectorStoreService,
    )
    from naas_abi_core.services.vector_store.adapters.QdrantAdapter import QdrantAdapter

    _ = Agent
    _ = IntentAgent
    _ = CacheService
    _ = CacheFactory
    _ = CachePort
    _ = CacheFSAdapter
    _ = EmailService
    _ = EmailFactory
    _ = IEmailAdapter
    _ = SMTPAdapter
    _ = ObjectStorageService
    _ = ObjectStorageSecondaryAdapterFS
    _ = ObjectStorageSecondaryAdapterNaas
    _ = ObjectStorageSecondaryAdapterS3
    _ = ObjectStorageSecondaryAdapterFS
    _ = ObjectStorageSecondaryAdapterNaas
    _ = ObjectStorageSecondaryAdapterS3
    _ = TripleStoreService
    _ = TripleStoreFactory
    _ = TripleStorePorts
    _ = ApacheJenaTDB2
    _ = AWSNeptune
    _ = Oxigraph
    _ = ObjectStorageSecondaryAdapterNaas
    _ = ObjectStorageSecondaryAdapterS3
    _ = TripleStoreService
    _ = TripleStoreFactory
    _ = Secret
    _ = SecretPorts
    _ = Base64Secret
    _ = dotenv_secret_secondaryadaptor
    _ = NaasSecret
    _ = VectorStoreFactory
    _ = VectorStoreService
    _ = IVectorStorePort
    _ = QdrantAdapter
    _ = VectorStoreService
    _ = IVectorStorePort
    _ = QdrantAdapter
