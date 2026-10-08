"""Optional OpenTelemetry tracing for ABI calls over NATS.

W3C trace context travels in NATS message headers (``traceparent``), so a call
from the API through an agent to the document service is one trace. Everything
here is a no-op when OpenTelemetry is not installed or no tracer provider is
configured. Importable without the NATS client (stdlib plus optional OTel).
"""

from __future__ import annotations

import contextlib
import os
import traceback
from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any

from naas_abi_sdk.redaction import scrub_secrets

TRACER_NAME = "naas_abi"
_configured = False


def record_span_exception(
    span: Any, error: BaseException, *, description: str | None = None
) -> None:
    """Record ``error`` on ``span`` as OpenTelemetry does (an ``exception``
    event, ERROR status), with credentials scrubbed from its message, stack
    trace and status: spans leave the process (Jaeger keeps a copy).

    ``description`` is the status text; by default ``"<Type>: <message>"``.
    """
    if span is None or not span.is_recording():
        return
    from opentelemetry.trace import Status, StatusCode

    message = scrub_secrets(str(error))
    stacktrace = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    span.record_exception(
        error,
        attributes={
            "exception.message": message,
            "exception.stacktrace": scrub_secrets(stacktrace),
        },
    )
    span.set_status(
        Status(
            StatusCode.ERROR,
            scrub_secrets(description)
            if description is not None
            else f"{type(error).__name__}: {message}",
        )
    )


@contextlib.contextmanager
def _recording_failures(span: Any) -> Iterator[None]:
    """What ``start_as_current_span`` does when the block raises, scrubbed.

    Spans opened here pass ``record_exception=False`` and
    ``set_status_on_exception=False``, so the raw text is never recorded.
    """
    try:
        yield
    except Exception as exc:  # OpenTelemetry records Exception, not BaseException
        record_span_exception(span, exc)
        raise


class TransferTrace:
    """One CLIENT span for a whole chunked transfer (object get/put, model stream).

    Passed explicitly to the chunk calls: never made "current" and no context
    variable, because a transfer may be driven from several tasks (a model stream
    is an async generator that callers advance from different contexts).
    """

    def __init__(self, span: Any = None) -> None:
        self.span = span
        self.messages = 0
        self.bytes_sent = 0
        self.bytes_received = 0

    def inject(self, headers: MutableMapping[str, str]) -> None:
        if self.span is None:
            return
        from opentelemetry import propagate, trace

        propagate.inject(headers, context=trace.set_span_in_context(self.span))

    def finish(self, error: BaseException | None = None) -> None:
        if self.span is None:
            return
        self.span.set_attribute("abi.transfer.messages", self.messages)
        self.span.set_attribute("abi.transfer.bytes_sent", self.bytes_sent)
        self.span.set_attribute("abi.transfer.bytes_received", self.bytes_received)
        if error is not None:
            record_span_exception(self.span, error, description=type(error).__name__)
        self.span.end()


class ServedTransfer(TransferTrace):
    """The owner's SERVER span for a transfer session it serves (``serve_transfer``).

    It lives from ``open`` until the session ends (close, idle expiry, stop), so it
    is ended explicitly, once. It is current only around the domain handler
    (``activate``). Totals are the owner's view: chunk data received and sent.
    """

    @contextlib.contextmanager
    def activate(self) -> Iterator[None]:
        """Make the span current, e.g. for the handler's task and its threads."""
        if self.span is None:
            yield
            return
        from opentelemetry import trace

        # Failures are recorded by ``fail`` with their ABI code, not here.
        with trace.use_span(
            self.span, record_exception=False, set_status_on_exception=False
        ):
            yield

    def fail(self, error: BaseException, code: str, message: str = "") -> None:
        """Record the real failure here; the caller only gets the sanitized code."""
        if self.span is None or not self.span.is_recording():
            return
        self.span.set_attribute("abi.error_code", code)
        record_span_exception(
            self.span, error, description=f"{code}: {message}" if message else code
        )

    def end(self, how: str, *, cancelled: bool = False) -> None:
        """End the span once: ``how`` the session ended, and whether its handler
        was still running (and is being cancelled)."""
        if self.span is None:
            return
        self.span.set_attribute("abi.transfer.end", how)
        self.span.set_attribute("abi.transfer.cancelled", cancelled)
        self.finish()
        self.span = None


def _api() -> Any | None:
    try:
        from opentelemetry import propagate, trace
    except ImportError:
        return None
    return trace, propagate


def _tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer(TRACER_NAME)


def describe_subject(subject: str) -> tuple[str, str]:
    """(service, method) of an ABI subject, for span names and attributes."""
    parts = subject.split(".")
    if subject.startswith("abi.svc.") and len(parts) >= 5:
        return parts[2], parts[-1]
    if subject.startswith("abi.discovery.") and len(parts) == 5:
        return "discovery", parts[4]
    if subject.startswith("abi.agent.") and len(parts) == 7:
        return "agent", parts[6]
    if subject.startswith("abi.jobs.") and len(parts) >= 4:
        return "jobs", parts[3]
    return "nats", subject


def _attributes(subject: str, extra: dict[str, Any] | None) -> dict[str, Any]:
    service, method = describe_subject(subject)
    attributes = {
        "rpc.system": "nats",
        "rpc.service": service,
        "rpc.method": method,
        "messaging.system": "nats",
        "messaging.destination.name": subject,
    }
    attributes.update(extra or {})
    return attributes


@contextlib.contextmanager
def client_span(
    subject: str,
    headers: MutableMapping[str, str],
    *,
    attributes: dict[str, Any] | None = None,
    size: int | None = None,
    transfer: TransferTrace | None = None,
) -> Iterator[Any]:
    """CLIENT span around a request on ``subject``; injects the trace into ``headers``.

    ``size``: request payload bytes. A chunk of a ``transfer`` opens no span of
    its own: it adds to the transfer's totals and carries the transfer's trace.
    """
    if transfer is not None:
        transfer.messages += 1
        transfer.bytes_sent += size or 0
        transfer.inject(headers)
        yield None
        return
    api = _api()
    if api is None:
        yield None
        return
    trace, propagate = api
    service, method = describe_subject(subject)
    extra = dict(attributes or {})
    if size is not None:
        extra["messaging.message.body.size"] = size
    with (
        _tracer().start_as_current_span(
            f"{service}/{method}",
            kind=trace.SpanKind.CLIENT,
            attributes=_attributes(subject, extra),
            record_exception=False,
            set_status_on_exception=False,
        ) as span,
        _recording_failures(span),
    ):
        propagate.inject(headers)
        yield span


def record_reply(size: int, *, transfer: TransferTrace | None = None) -> None:
    """Reply payload bytes of the current call (or of a transfer's chunk)."""
    if transfer is not None:
        transfer.bytes_received += size
        return
    api = _api()
    if api is None:
        return
    trace, _ = api
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("abi.reply.body.size", size)


def record_overflow(overflow: TransferTrace) -> None:
    """Totals of an RPC's overflow exchanges (payloads above the broker limit),
    on the call's own CLIENT span. Nothing when the call did not overflow."""
    if overflow.span is None or not overflow.messages:
        return
    overflow.span.set_attribute("abi.overflow.messages", overflow.messages)
    overflow.span.set_attribute("abi.overflow.bytes_sent", overflow.bytes_sent)
    overflow.span.set_attribute("abi.overflow.bytes_received", overflow.bytes_received)


@contextlib.contextmanager
def transfer_span(prefix: str, operation: str) -> Iterator[TransferTrace]:
    """A ``TransferTrace`` for a chunked transfer on ``prefix`` (e.g.
    ``abi.svc.object_storage.v1.transfer``): pass it to every chunk call."""
    api = _api()
    if api is None:
        yield TransferTrace()
        return
    trace, _ = api
    service, _ = describe_subject(f"{prefix}.{operation}")
    span = _tracer().start_span(
        f"{service}/transfer.{operation}",
        kind=trace.SpanKind.CLIENT,
        attributes=_attributes(prefix, {"abi.transfer.operation": operation}),
    )
    transfer = TransferTrace(span)
    try:
        yield transfer
    except BaseException as exc:
        transfer.finish(exc)
        raise
    transfer.finish()


def serve_transfer(
    prefix: str,
    operation: str,
    headers: Mapping[str, str] | None,
    *,
    attributes: dict[str, Any] | None = None,
) -> ServedTransfer:
    """Start the SERVER span of a transfer session opened on ``prefix``.

    Continues the trace in the ``open`` request's headers (the caller's transfer
    span) and has the same name. Not current: see ``ServedTransfer``.
    """
    api = _api()
    if api is None:
        return ServedTransfer()
    trace, propagate = api
    service, _ = describe_subject(f"{prefix}.{operation}")
    extra = {"abi.transfer.operation": operation, **(attributes or {})}
    return ServedTransfer(
        _tracer().start_span(
            f"{service}/transfer.{operation}",
            context=propagate.extract(dict(headers or {})),
            kind=trace.SpanKind.SERVER,
            attributes=_attributes(prefix, extra),
        )
    )


@contextlib.contextmanager
def server_span(
    subject: str,
    headers: MutableMapping[str, str] | None,
    *,
    kind: str = "server",
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """SERVER (or CONSUMER) span for a message, continuing the trace in its headers."""
    api = _api()
    if api is None:
        yield None
        return
    trace, propagate = api
    service, method = describe_subject(subject)
    span_kind = trace.SpanKind.CONSUMER if kind == "consumer" else trace.SpanKind.SERVER
    with (
        _tracer().start_as_current_span(
            name or f"{service}/{method}",
            context=propagate.extract(dict(headers or {})),
            kind=span_kind,
            attributes=_attributes(subject, attributes),
            record_exception=False,
            set_status_on_exception=False,
        ) as span,
        _recording_failures(span),
    ):
        yield span


@contextlib.contextmanager
def internal_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
    """INTERNAL span (e.g. an agent run) under the current span."""
    if _api() is None:
        yield None
        return
    with (
        _tracer().start_as_current_span(
            name,
            attributes=attributes or {},
            record_exception=False,
            set_status_on_exception=False,
        ) as span,
        _recording_failures(span),
    ):
        yield span


def current_trace_id() -> str:
    """The current span's trace id (32 hex), or ``""`` without tracing."""
    api = _api()
    if api is None:
        return ""
    trace, _ = api
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return ""
    return format(context.trace_id, "032x")


def record_error(code: str, message: str = "") -> None:
    """Mark the current span failed with an ABI error code (no-op without tracing)."""
    api = _api()
    if api is None:
        return
    trace, _ = api
    span = trace.get_current_span()
    if not span.is_recording():
        return
    from opentelemetry.trace import Status, StatusCode

    span.set_attribute("abi.error_code", code)
    description = f"{code}: {scrub_secrets(message)}" if message else code
    span.set_status(Status(StatusCode.ERROR, description))


def configure_tracing(
    service_name: str, *, endpoint: str | None = None, sample_ratio: float = 1.0
) -> bool:
    """Install an OTLP/HTTP exporting tracer provider once per process.

    ``endpoint`` is the collector base URL (``http://jaeger:4318``); without it the
    exporter reads the standard ``OTEL_EXPORTER_OTLP_*`` variables. Returns False
    when the OpenTelemetry SDK is not installed or tracing is already configured.
    """
    global _configured
    if _configured:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        return False
    exporter = OTLPSpanExporter(
        endpoint=f"{endpoint.rstrip('/')}/v1/traces" if endpoint else None
    )
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name}),
        sampler=ParentBased(TraceIdRatioBased(sample_ratio)),
    )
    # Exported every second (default 5): the System app shows recent spans live.
    provider.add_span_processor(
        BatchSpanProcessor(exporter, schedule_delay_millis=1000)
    )
    trace.set_tracer_provider(provider)
    _configured = True
    return True


def configure_from_env(default_service_name: str) -> bool:
    """Configure tracing when ``OTEL_EXPORTER_OTLP_(TRACES_)ENDPOINT`` is set."""
    if not (
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    ):
        return False
    return configure_tracing(
        os.environ.get("OTEL_SERVICE_NAME") or default_service_name
    )
