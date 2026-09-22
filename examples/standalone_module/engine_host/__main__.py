"""Engine process; the isolated worker never imports this module."""

import json
import os
import signal
import threading
from pathlib import Path

from naas_abi_core import logger
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.engine.nats_auth import issue_service_token

logger.remove()  # Configuration debug logging can contain the demo signing key.
logger.add(lambda message: print(message, end="", flush=True), level="WARNING")
root = Path(os.environ["DEMO_DATA"])
url = os.environ["DEMO_NATS_URL"]
(root / "demo.env").touch(mode=0o600)
engine = Engine(
    json.dumps(
        {
            "api": {},
            "global_config": {"ai_mode": "cloud", "skip_ontology_loading": True},
            "modules": [{"module": "engine_host", "enabled": True}],
            "nats": {"nats_url": url, "jwt_secret": os.environ["DEMO_SIGNING_KEY"]},
            "services": {
                "secret": {
                    "secret_adapters": [
                        {
                            "adapter": "dotenv",
                            "config": {"path": str(root / "demo.env")},
                        }
                    ]
                },
                "bus": {
                    "bus_adapter": {
                        "adapter": "nats_jetstream",
                        "config": {"nats_url": url},
                    }
                },
                "email": {
                    "email_adapter": {
                        "adapter": "filesystem",
                        "config": {"directory": str(root / "email")},
                    }
                },
                "cache": {
                    "adapters": [
                        {
                            "adapter": "fs",
                            "tier": "cold",
                            "config": {"base_path": str(root / "cache")},
                        }
                    ]
                },
            },
        }
    )
)
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())
try:
    engine.load()

    def echo(payload):
        engine.services.bus.publish("demo.reply", "echo", payload)

    def work(payload):
        engine.services.bus.enqueue("demo.outbox", "work", payload)
        raise StopIteration

    engine.services.bus.subscribe("demo.inbox", "echo", echo)
    engine.services.bus.dequeue("demo.jobs", "work", work)
    token = root / "token"
    token.touch(mode=0o600)
    token.write_text(
        issue_service_token("standalone-demo", os.environ["DEMO_SIGNING_KEY"])
    )
    (root / "ready.json").write_text(json.dumps({"engine_pid": os.getpid()}))
    stop.wait()
finally:
    engine.shutdown()
