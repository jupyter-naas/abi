"""Install OpenTelemetry tracing for this engine process (``telemetry:`` config)."""

from __future__ import annotations

from collections.abc import Callable

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    TelemetryConfiguration,
)


def _install(service_name: str, *, endpoint: str | None, sample_ratio: float) -> bool:
    try:
        from naas_abi_sdk.telemetry import configure_tracing
    except ImportError:
        return False
    return configure_tracing(service_name, endpoint=endpoint, sample_ratio=sample_ratio)


def configure(
    config: TelemetryConfiguration, *, install: Callable[..., bool] = _install
) -> bool:
    """True when tracing was installed; never fails the engine."""
    if not config.enabled:
        return False
    installed = install(
        config.service_name,
        endpoint=config.otlp_endpoint,
        sample_ratio=config.sample_ratio,
    )
    if installed:
        logger.info(
            f"Tracing: exporting spans as {config.service_name!r} to "
            f"{config.otlp_endpoint or 'the OTEL_EXPORTER_OTLP_* endpoint'}"
        )
    else:
        logger.warning(
            "telemetry.enabled is set but tracing was not installed: it needs "
            "naas-abi-core[otel], or tracing was already configured in this process"
        )
    return installed
