# This is used to test all imports and ensure all libraries are installed and imported correctly.


def test_imports():
    from naas_abi_core.services.agent import Agent, IntentAgent
    from naas_abi_core.services.cache import CacheFactory, CachePort, CacheService
    from naas_abi_core.services.cache.adapters.secondary import CacheFSAdapter
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
        AWSNeptune,
        Oxigraph,
    )
    from naas_abi_core.services.vector_store import (
        IVectorStorePort,
        VectorStoreFactory,
        VectorStoreService,
    )
    from naas_abi_core.services.vector_store.adapters.QdrantAdapter import QdrantAdapter

    Agent
    IntentAgent
    CacheService
    CacheFactory
    CachePort
    CacheFSAdapter
    ObjectStorageService
    ObjectStorageSecondaryAdapterFS
    ObjectStorageSecondaryAdapterNaas
    ObjectStorageSecondaryAdapterS3
    ObjectStorageSecondaryAdapterFS
    ObjectStorageSecondaryAdapterNaas
    ObjectStorageSecondaryAdapterS3
    TripleStoreService
    TripleStoreFactory
    TripleStorePorts
    AWSNeptune
    Oxigraph
    ObjectStorageSecondaryAdapterNaas
    ObjectStorageSecondaryAdapterS3
    TripleStoreService
    TripleStoreFactory
    Secret
    SecretPorts
    Base64Secret
    dotenv_secret_secondaryadaptor
    NaasSecret
    VectorStoreFactory
    VectorStoreService
    IVectorStorePort
    QdrantAdapter
    VectorStoreService
    IVectorStorePort
    QdrantAdapter
