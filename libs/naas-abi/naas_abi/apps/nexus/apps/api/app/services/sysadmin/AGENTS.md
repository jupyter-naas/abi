# SysAdmin domain

Views of a running deployment for platform super admins: kernel services (configuration plus NATS micro-service stats), engine modules, remote modules in NATS discovery, the broker (server, connections, JetStream), and live NATS traffic.

## Layout

- `port.py`: domain values and ports (`ServiceConfigurationSource`, `EngineModuleSource`, `MicroServiceMonitor`, `ModuleRegistry`, `NatsServerMonitor`). Adapters raise `SourceUnavailable(source, reason)`; nothing else crosses a port.
- `service.py`: use cases. Views degrade per source and report `sources: {name: {available, reason}}`.
- `adapters/secondary/`: engine configuration (adapter kinds only, never settings), engine modules, `$SRV.STATS` scatter-gather, discovery, the broker HTTP monitor (`nats.monitoring_url`), in-memory fakes.
- `adapters/primary/`: FastAPI router (`/api/admin/system/*`, `require_superadmin` on the router) and the JSON serializer (dataclass fields plus computed properties).
- `traffic.py`: live traffic. `TrafficEvent` (metadata only), subject classification, caller from the token's `sub`, trace id from `traceparent`, and `TrafficHub` (one tap while a viewer watches, bounded per-viewer queues that drop oldest). `adapters/secondary/nats_traffic_tap.py` subscribes to ABI request subjects plus `_INBOX.>` to pair replies; transfer subjects are excluded. Served as SSE at `/api/admin/system/traffic/stream`. Source order (`FallbackTap`): `JaegerSpanTap` (recent spans from the tracing backend, `telemetry.query_url`) first, the NATS tap second; the first frame names the live source and why others were skipped.
- `GET /telemetry`: tracing as configured (`telemetry:` in the engine config); the web links trace ids to `ui_url/trace/<id>`. HTTP spans come from `app/core/tracing.py`.
- `factory.py`: wires adapters from `engine.configuration` (identity `api`, connection name `nexus-api-sysadmin`, bounded connect time).
- `contracts.py`: one contract per port. A new adapter's test subclasses it with a fixture describing `tests/fixtures.py`'s deployment.

## Rules

- Never read or return adapter settings, tokens or message payloads. Traffic reads headers and sizes only.
- The tap receives every reply on the bus while it runs: it starts with the first viewer and stops with the last. Never start it in the background.
- NATS calls must stay bounded: a dashboard never waits on nats-py's reconnect loop.
- `adapters/secondary/nats_integration_test.py` runs both NATS adapters against a real `nats-server -js -m`; run it after changing them.
