# `telemetry` (OpenTelemetry helpers)

## What it is
- Optional OpenTelemetry tracing utilities for ABI calls over NATS.
- Propagates W3C trace context via NATS headers (e.g. `traceparent`) so multi-hop calls remain a single trace.
- Safe to import and use when OpenTelemetry is not installed or not configured: most functions become no-ops.

## Public API

### Constants
- `TRACER_NAME`: Tracer name used when creating spans (`"naas_abi"`).

### Classes
- `TransferTrace(span: Any = None)`
  - Tracks a whole chunked transfer as one CLIENT span (counts messages, bytes sent/received).
  - Methods:
    - `inject(headers: MutableMapping[str, str]) -> None`: injects the transfer span context into headers.
    - `finish(error: BaseException | None = None) -> None`: sets transfer totals, records an optional error, ends span.

- `ServedTransfer(span: Any = None)` (subclass of `TransferTrace`)
  - Represents the SERVER span on the service side for a transfer session.
  - Methods:
    - `activate() -> contextmanager`: makes the span current while running the domain handler.
    - `fail(error: BaseException, code: str, message: str = "") -> None`: records an error with ABI error code on the span.
    - `end(how: str, *, cancelled: bool = False) -> None`: sets end attributes, finalizes and ends span (only once).

### Functions
- `describe_subject(subject: str) -> tuple[str, str]`
  - Maps an ABI/NATS subject to `(service, method)` used in span naming/attributes.

- `client_span(subject: str, headers: MutableMapping[str, str], *, attributes: dict[str, Any] | None = None, size: int | None = None, transfer: TransferTrace | None = None) -> contextmanager`
  - Creates a CLIENT span for an RPC request and injects trace context into `headers`.
  - If `transfer` is provided, does not create a span: increments transfer totals and injects transfer context.

- `record_reply(size: int, *, transfer: TransferTrace | None = None) -> None`
  - Records reply payload size on the current span (`abi.reply.body.size`), or updates transfer totals when `transfer` is provided.

- `record_overflow(overflow: TransferTrace) -> None`
  - Records overflow-exchange totals on the overflow span (when `overflow.span` exists and `overflow.messages > 0`).

- `transfer_span(prefix: str, operation: str) -> contextmanager[TransferTrace]`
  - Creates a CLIENT span for a chunked transfer session and returns a `TransferTrace` to be passed to each chunk RPC.

- `serve_transfer(prefix: str, operation: str, headers: Mapping[str, str] | None, *, attributes: dict[str, Any] | None = None) -> ServedTransfer`
  - Starts the SERVER span for a transfer session, continuing the trace from the `open` request headers.

- `server_span(subject: str, headers: MutableMapping[str, str] | None, *, kind: str = "server", name: str | None = None, attributes: dict[str, Any] | None = None) -> contextmanager`
  - Creates a SERVER (default) or CONSUMER span for an incoming message, continuing trace context from headers.

- `internal_span(name: str, attributes: dict[str, Any] | None = None) -> contextmanager`
  - Creates an INTERNAL span under the current span (e.g., for internal agent work).

- `current_trace_id() -> str`
  - Returns the current trace id as 32 hex chars, or `""` if tracing is unavailable/invalid.

- `record_error(code: str, message: str = "") -> None`
  - Marks the current span as failed with ABI error code (`abi.error_code`) and ERROR status.

- `configure_tracing(service_name: str, *, endpoint: str | None = None, sample_ratio: float = 1.0) -> bool`
  - Installs an OTLP/HTTP exporting tracer provider once per process.
  - Returns `False` if already configured or if OpenTelemetry SDK/exporter is not installed.

- `configure_from_env(default_service_name: str) -> bool`
  - Configures tracing only when `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set.

## Configuration/Dependencies
- Hard dependency: `naas_abi_sdk.redaction.scrub_secrets` (used to scrub credentials from recorded exception text/stack traces).
- Optional dependencies (only required to actually trace/export):
  - `opentelemetry-api` (for context propagation and span APIs)
  - `opentelemetry-sdk`
  - `opentelemetry-exporter-otlp-proto-http`
- Environment variables used:
  - `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` (enables `configure_from_env`)
  - `OTEL_SERVICE_NAME` (service name override)
- `configure_tracing(..., endpoint=...)` uses OTLP/HTTP traces endpoint:
  - If `endpoint` is provided, exporter endpoint becomes `"{endpoint.rstrip('/')}/v1/traces"`.

## Usage

### Configure tracing (optional)
```python
from naas_abi_sdk.telemetry import configure_tracing

configure_tracing(service_name="my-service", endpoint="http://jaeger:4318", sample_ratio=1.0)
```

### Trace an RPC client call and propagate headers
```python
from naas_abi_sdk.telemetry import client_span, record_reply

headers = {}
subject = "abi.svc.object_storage.v1.get"

with client_span(subject, headers, size=123) as span:
    # send request with `headers`
    # ...
    record_reply(456)  # record reply size on the current span
```

### Trace a chunked transfer (single span across chunks)
```python
from naas_abi_sdk.telemetry import transfer_span, client_span, record_reply

prefix = "abi.svc.object_storage.v1.transfer"

with transfer_span(prefix, "put") as transfer:
    headers = {}
    with client_span(f"{prefix}.chunk", headers, size=1024, transfer=transfer):
        # send a chunk with `headers`
        record_reply(64, transfer=transfer)  # update transfer totals
```

### Trace a server handler and continue incoming context
```python
from naas_abi_sdk.telemetry import server_span, record_error

subject = "abi.svc.object_storage.v1.get"
headers = {"traceparent": "..."}  # from NATS message headers

with server_span(subject, headers):
    try:
        # handle message
        pass
    except Exception as e:
        record_error("INTERNAL", str(e))
        raise
```

## Caveats
- Exception recording is scrubbed (message, stacktrace, status text) to avoid leaking secrets to external tracing backends.
- Spans created by these context managers disable OpenTelemetry’s default exception/status-on-exception behavior and replace it with scrubbed recording via internal helpers.
- `configure_tracing()` is single-shot per process; subsequent calls return `False`.
