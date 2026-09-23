"""Async service facades: Python arguments and results, no engine dependency."""

from naas_abi_sdk.services._activity_log import ActivityLogService
from naas_abi_sdk.services._coding_environment import CodingEnvironmentService
from naas_abi_sdk.services._dataset import DatasetService
from naas_abi_sdk.services._email import EmailService
from naas_abi_sdk.services._source_control import SourceControlService
from naas_abi_sdk.services.cache import CacheService
from naas_abi_sdk.services.document import DocumentService
from naas_abi_sdk.services.event import EventService
from naas_abi_sdk.services.keyvalue import KeyValueService
from naas_abi_sdk.services.model_registry import ModelRegistryService
from naas_abi_sdk.services.object_storage import ObjectStorageService
from naas_abi_sdk.services.secret import SecretService
from naas_abi_sdk.services.triple_store import TripleStoreService
from naas_abi_sdk.services.vector_store import VectorStoreService

FACTORIES = {
    "model_registry": ModelRegistryService,
    "object_storage": ObjectStorageService,
    "keyvalue": KeyValueService,
    "secret": SecretService,
    "cache": CacheService,
    "document": DocumentService,
    "email": EmailService,
    "activity_log": ActivityLogService,
    "source_control": SourceControlService,
    "coding_environment": CodingEnvironmentService,
    "dataset": DatasetService,
    "triple_store": TripleStoreService,
    "vector_store": VectorStoreService,
}


def service_proxy(name, client, bus):
    if name == "bus":
        return client
    if name == "event":
        return EventService(client, bus)
    return FACTORIES[name](client)
