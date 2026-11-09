"""Native NATS bus, wire-compatible with the engine's NATSJetStreamAdapter.

Subscriptions return nats-py handles whose messages carry their full payload:
a message above the broker limit travels as a claim check (claim_check.py) and
is read back before the caller sees it. A dequeued message must be explicitly
acked after processing, or nacked on failure. Redelivery is at least once.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Sequence
from typing import Any

from nats.aio.subscription import Subscription
from nats.js.client import JetStreamContext
from nats.js.errors import BadRequestError, NotFoundError

from naas_abi_sdk import claim_check
from naas_abi_sdk.broker_flush import flush_to_broker
from naas_abi_sdk.transport import Transport


class ClaimCheckedSubscription:
    """A nats-py subscription whose messages carry their stored payload."""

    def __init__(
        self,
        nc: Any,
        subscription: Subscription,
        store: claim_check.ThroughEngine | None = None,
    ) -> None:
        self._nc, self._subscription, self._store = nc, subscription, store

    async def next_msg(self, timeout: float = 1.0) -> Any:
        msg = await self._subscription.next_msg(timeout=timeout)
        return await claim_check.resolve_in_place(self._nc, msg, store=self._store)

    @property
    async def messages(self) -> Any:
        async for msg in self._subscription.messages:
            yield await claim_check.resolve_in_place(self._nc, msg, store=self._store)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._subscription, name)


class ClaimCheckedPullSubscription:
    """A JetStream pull subscription whose messages carry their stored payload."""

    def __init__(
        self,
        nc: Any,
        subscription: Any,
        store: claim_check.ThroughEngine | None = None,
    ) -> None:
        self._nc, self._subscription, self._store = nc, subscription, store

    async def fetch(self, batch: int = 1, timeout: float | None = 5, **kwargs: Any):
        msgs = await self._subscription.fetch(batch, timeout, **kwargs)
        for msg in msgs:
            await claim_check.resolve_in_place(self._nc, msg, store=self._store)
        return msgs

    def __getattr__(self, name: str) -> Any:
        return getattr(self._subscription, name)


async def ensure_topic_stream(js: JetStreamContext, topic: str) -> str:
    """The queue stream of ``topic``, created if missing. Behind the broker's
    auth callout the engine does it (``BrokerControl``): a module may create
    no stream."""
    name = BusClient.stream_name(topic)
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


def queue_consumer_config(topic: str, routing_key: str) -> Any:
    """The durable pull consumer ``dequeue`` reads (shared by every reader)."""
    from nats.js.api import ConsumerConfig

    name = BusClient.consumer_name(topic, routing_key)
    return ConsumerConfig(
        name=name,
        durable_name=name,
        filter_subject=BusClient.subject(topic, routing_key),
    )


async def ensure_queue(js: JetStreamContext, topic: str, routing_key: str) -> str:
    """The queue stream and its consumer for ``routing_key``, created if missing."""
    stream = await ensure_topic_stream(js, topic)
    config = queue_consumer_config(topic, routing_key)
    try:
        await js.consumer_info(stream, config.durable_name)
    except NotFoundError:
        await js.add_consumer(stream, config)
    return stream


class BusClient:
    def __init__(self, transport: Transport) -> None:
        from naas_abi_sdk.broker_control import for_transport

        self._transport = transport
        self._control = for_transport(transport)
        self._claims = claim_check.ThroughEngine(self._control)
        self._queues: set[str] = set()  # topics whose queue stream exists

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
        nc = await self._transport.connect()
        body, headers = await claim_check.prepare(
            nc,
            payload,
            scope=claim_check.topic_scope(topic),
            store=self._claims,
        )

        async def send():
            await nc.publish(self.subject(topic, routing_key), body, headers=headers)
            await flush_to_broker(nc)

        await asyncio.wait_for(send(), self._transport.timeout)

    async def publish_many(
        self, topic: str, messages: Sequence[tuple[str, bytes]]
    ) -> None:
        """Publish in order; a partial failure is not retried or rolled back."""
        for routing_key, payload in messages:
            await self.publish(topic, routing_key, payload)

    async def subscribe(self, topic: str, routing_key: str) -> ClaimCheckedSubscription:
        async def subscribe():
            nc = await self._transport.connect()
            sub = await nc.subscribe(self.subject(topic, routing_key))
            await flush_to_broker(nc)
            return ClaimCheckedSubscription(nc, sub, self._claims)

        return await asyncio.wait_for(subscribe(), self._transport.timeout)

    async def _stream(self, js: JetStreamContext, topic: str) -> str:
        """The topic's queue stream: through the engine when it answers."""
        if await self._control.request("ensure_topic", topic=topic):
            return self.stream_name(topic)
        return await ensure_topic_stream(js, topic)

    async def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        from nats.js.errors import NoStreamResponseError

        nc = await self._transport.connect()
        js = nc.jetstream()
        stream = self.stream_name(topic)
        subject = self.subject(topic, routing_key)
        if topic not in self._queues:
            # Before the first message: a pub/sub subscriber of the subject
            # would otherwise answer for the missing stream (no ack, a timeout).
            await asyncio.wait_for(self._stream(js, topic), self._transport.timeout)
            self._queues.add(topic)
        body, headers = await claim_check.prepare(
            nc,
            payload,
            scope=claim_check.topic_scope(topic),
            reserve=claim_check.stream_header_reserve(stream),
            store=self._claims,
        )
        try:
            await asyncio.wait_for(
                js.publish(subject, body, stream=stream, headers=headers),
                self._transport.timeout,
            )
        except NoStreamResponseError:
            # The first message on this topic: its stream does not exist yet.
            await asyncio.wait_for(self._stream(js, topic), self._transport.timeout)
            await asyncio.wait_for(
                js.publish(subject, body, stream=stream, headers=headers),
                self._transport.timeout,
            )

    async def dequeue(
        self, topic: str, routing_key: str
    ) -> ClaimCheckedPullSubscription:
        """Return a durable pull subscription; use fetch(), then msg.ack()/nak()."""

        async def subscribe():
            nc = await self._transport.connect()
            js = nc.jetstream()
            durable = self.consumer_name(topic, routing_key)
            if await self._control.request(
                "ensure_queue", topic=topic, routing_key=routing_key
            ):
                stream = self.stream_name(topic)
            else:
                stream = await ensure_queue(js, topic, routing_key)
            return ClaimCheckedPullSubscription(
                nc,
                await js.pull_subscribe_bind(
                    durable=durable, stream=stream, name=durable
                ),
                self._claims,
            )

        return await asyncio.wait_for(subscribe(), self._transport.timeout)
