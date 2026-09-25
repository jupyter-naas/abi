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
            "nats": {
                "nats_url": url,
                "jwt_secret": os.environ["DEMO_SIGNING_KEY"],
                "discovery": {"lease_seconds": 2},
            },
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
                            "adapter": "keyvalue",
                            "tier": "hot",
                            "config": {"cache_prefix": "hot-cache"},
                        },
                        {
                            "adapter": "object_storage",
                            "tier": "cold",
                            "config": {"cache_prefix": "cache"},
                        },
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
    from langchain_core.embeddings import DeterministicFakeEmbedding
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from naas_abi_core.models.Model import ChatModel, EmbeddingModel

    engine.services.model_registry.register(
        "demo-chat",
        ChatModel(
            model_id="fake",
            provider="demo",
            model=FakeListChatModel(responses=["remote model answer"]),
        ),
    )
    engine.services.model_registry.register(
        "demo-agent-chat",
        ChatModel(
            model_id="fake-agent",
            provider="demo",
            model=FakeListChatModel(
                responses=[f"remote agent answer from PID {os.getpid()}"]
            ),
        ),
    )
    engine.services.model_registry.register(
        "demo-embedding",
        EmbeddingModel(
            model_id="fake-embedding",
            provider="demo",
            model=DeterministicFakeEmbedding(size=8),
        ),
    )

    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from naas_abi_core.engine import nats_runtime

    async def constrain_shared_pool():
        asyncio.get_running_loop().set_default_executor(
            ThreadPoolExecutor(max_workers=1)
        )

    nats_runtime.run_coro(constrain_shared_pool())
    seen = set()
    from collections import Counter

    from naas_abi_proto.event.v1.event_pb2 import AppendRequest

    event_counts = Counter()

    async def observe(msg):
        subject = msg.subject
        if ".transfer." in subject and len(subject.split(".")) == 7:
            parts = subject.split(".")
            subject = ".".join(parts[:5] + parts[6:])
        seen.add(subject)
        if msg.subject == "abi.svc.event.v1.append":
            event_counts[AppendRequest.FromString(msg.data).event_type] += 1

    nc = nats_runtime.get_connection(url)
    subscription = nats_runtime.run_coro(nc.subscribe("abi.svc.>", cb=observe))
    nats_runtime.run_coro(nc.flush())
    # Invoke the owning cache service. Its dependencies must cross the broker,
    # even though their owners happen to be in this same engine process.
    engine.services.cache.cold.set_text("boundary", "cold")
    assert engine.services.cache.cold.get("boundary") == "cold"
    engine.services.cache.hot.set_text("boundary", "hot")
    assert engine.services.cache.hot.get("boundary") == "hot"
    engine.services.cache.delete("boundary")
    nats_runtime.run_coro(nc.flush())
    required = {
        "abi.svc.object_storage.v1.transfer.write",
        "abi.svc.object_storage.v1.transfer.read",
        "abi.svc.keyvalue.v1.set",
        "abi.svc.keyvalue.v1.get",
        "abi.svc.event.v1.append",
    }
    assert required <= seen, f"Missing cross-domain NATS traffic: {required - seen}"
    assert event_counts["http://ontology.naas.ai/abi/object_storage/ObjectPut"] == 1
    assert event_counts["http://ontology.naas.ai/abi/keyvalue/KeyValueSet"] == 1
    nats_runtime.run_coro(subscription.unsubscribe())

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
    (root / "ready.json").write_text(
        json.dumps(
            {
                "engine_pid": os.getpid(),
                "cross_domain_subjects": sorted(seen),
                "cross_domain_event_counts": dict(event_counts),
            }
        )
    )
    stop.wait()
finally:
    engine.shutdown()
