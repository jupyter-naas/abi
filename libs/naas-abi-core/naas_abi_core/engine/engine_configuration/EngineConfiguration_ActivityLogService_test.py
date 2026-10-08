from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    ServicesConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ActivityLogService import (
    ActivityLogAdapterConfiguration,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogDocumentAdapter import (
    ActivityLogDocumentAdapter,
)


def test_the_activity_log_lives_in_the_document_service_by_default():
    adapter = ServicesConfiguration().activity_log.activity_log_adapter

    assert adapter.adapter == "document"
    assert isinstance(adapter.load(), ActivityLogDocumentAdapter)


def test_the_document_adapter_needs_no_config():
    assert ActivityLogAdapterConfiguration(adapter="document").config is None
