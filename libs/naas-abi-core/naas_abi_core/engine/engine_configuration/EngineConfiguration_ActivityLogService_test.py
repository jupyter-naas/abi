from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
    ServicesConfiguration,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ActivityLogService import (
    ActivityLogAdapterConfiguration,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogDocumentAdapter import (
    ActivityLogDocumentAdapter,
)


def engine_configuration(**top_level) -> EngineConfiguration:
    return EngineConfiguration.model_validate(
        {
            "api": {},
            "global_config": {"ai_mode": "cloud"},
            "modules": [],
            "services": top_level.pop("services", {"secret": {"secret_adapters": []}}),
            **top_level,
        }
    )


def test_the_activity_log_lives_in_the_document_service_by_default():
    adapter = ServicesConfiguration().activity_log.activity_log_adapter

    assert adapter.adapter == "document"
    assert isinstance(adapter.load(), ActivityLogDocumentAdapter)


def test_in_nats_mode_the_default_is_the_document_service():
    configuration = engine_configuration(nats={"jwt_secret": "x" * 32})

    assert configuration.services.activity_log.activity_log_adapter.adapter == "document"


def test_without_nats_the_default_stays_the_2x_sqlite_log():
    configuration = engine_configuration()
    adapter = configuration.services.activity_log.activity_log_adapter

    assert adapter.adapter == "sqlite"
    assert adapter.config.data_dir == "storage/activity_log"
    # Still a default: the System app lists only services the config sets.
    assert "activity_log" not in configuration.services.model_fields_set


def test_an_explicit_adapter_wins_without_nats():
    configuration = engine_configuration(
        services={
            "secret": {"secret_adapters": []},
            "activity_log": {"activity_log_adapter": {"adapter": "document"}},
        }
    )

    assert configuration.services.activity_log.activity_log_adapter.adapter == "document"


def test_the_document_adapter_needs_no_config():
    assert ActivityLogAdapterConfiguration(adapter="document").config is None
