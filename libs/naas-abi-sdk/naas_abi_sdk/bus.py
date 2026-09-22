"""Native NATS bus, wire-compatible with the engine's NATSJetStreamAdapter.

Subscriptions return nats-py handles. A dequeued message must be explicitly
acked after processing, or nacked on failure. Redelivery is at least once.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Sequence

from nats.aio.subscription import Subscription
from nats.js.client import JetStreamContext
from nats.js.errors import BadRequestError, NotFoundError

from naas_abi_sdk.transport import Transport


class BusClient:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    @staticmethod
    def stream_name(topic: str) -> str:
        return "naas-abi-" + hashlib.sha256(topic.encode()).hexdigest()

    @staticmethod
    def consumer_name(topic: str, routing_key: str) -> str:
        return (
            "naas-abi-" + hashlib.sha256(f"{topic}:{routing_key}".encode()).hexdigest()
        )

    @staticmethod
    def subject(topic: str, routing_key: str) -> str:
        if not topic or not routing_key:
            raise ValueError("topic and routing_key must be nonempty")
        if "#" in routing_key.split(".")[:-1]:
            raise ValueError("Only trailing # wildcards can map to NATS")
        return f"{topic}.{routing_key}".removesuffix("#") + (
            ">" if routing_key.endswith("#") else ""
        )

    async def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        async def send():
            nc = await self._transport.connect()
            await nc.publish(self.subject(topic, routing_key), payload)
            await nc.flush()

        await asyncio.wait_for(send(), self._transport.timeout)

    async def publish_many(
        self, topic: str, messages: Sequence[tuple[str, bytes]]
    ) -> None:
        """Publish in order; a partial failure is not retried or rolled back."""
        for routing_key, payload in messages:
            await self.publish(topic, routing_key, payload)

    async def subscribe(self, topic: str, routing_key: str) -> Subscription:
        async def subscribe():
            nc = await self._transport.connect()
            sub = await nc.subscribe(self.subject(topic, routing_key))
            await nc.flush()
            return sub

        return await asyncio.wait_for(subscribe(), self._transport.timeout)

    async def _stream(self, js: JetStreamContext, topic: str) -> str:
        name = self.stream_name(topic)
        try:
            info = await js.stream_info(name)
        except NotFoundError:
            try:
                info = await js.add_stream(name=name, subjects=[f"{topic}.>"])
            except BadRequestError:
                info = await js.stream_info(name)
        if info.config.subjects != [f"{topic}.>"]:
            raise ValueError("Existing stream has incompatible subjects")
        return name

    async def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        async def send():
            nc = await self._transport.connect()
            js = nc.jetstream()
            stream = await self._stream(js, topic)
            await js.publish(self.subject(topic, routing_key), payload, stream=stream)

        await asyncio.wait_for(send(), self._transport.timeout)

    async def dequeue(
        self, topic: str, routing_key: str
    ) -> JetStreamContext.PullSubscription:
        """Return a durable pull subscription; use fetch(), then msg.ack()/nak()."""

        async def subscribe():
            nc = await self._transport.connect()
            js = nc.jetstream()
            stream = await self._stream(js, topic)
            return await js.pull_subscribe(
                self.subject(topic, routing_key),
                durable=self.consumer_name(topic, routing_key),
                stream=stream,
            )

        return await asyncio.wait_for(subscribe(), self._transport.timeout)
