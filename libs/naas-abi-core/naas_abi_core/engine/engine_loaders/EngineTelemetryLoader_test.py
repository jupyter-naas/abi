import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    TelemetryConfiguration,
)
from naas_abi_core.engine.engine_loaders import EngineTelemetryLoader as loader
from pydantic import ValidationError


def test_tracing_is_opt_in():
    calls = []
    assert (
        loader.configure(
            TelemetryConfiguration(), install=lambda *a, **k: calls.append(1)
        )
        is False
    )
    assert calls == []


def test_enabled_tracing_installs_the_exporter_with_the_configuration():
    calls = []

    def install(service_name, *, endpoint, sample_ratio):
        calls.append((service_name, endpoint, sample_ratio))
        return True

    config = TelemetryConfiguration(
        enabled=True,
        otlp_endpoint="http://jaeger:4318",
        service_name="zen-engine",
        sample_ratio=0.5,
    )

    assert loader.configure(config, install=install) is True
    assert calls == [("zen-engine", "http://jaeger:4318", 0.5)]


def test_missing_otel_extra_is_reported_not_fatal(caplog):
    def install(*args, **kwargs):
        return False

    assert (
        loader.configure(TelemetryConfiguration(enabled=True), install=install) is False
    )


@pytest.mark.parametrize("field", ["otlp_endpoint", "ui_url"])
def test_urls_must_be_http(field):
    with pytest.raises(ValidationError):
        TelemetryConfiguration(**{field: "grpc://collector:4317"})
