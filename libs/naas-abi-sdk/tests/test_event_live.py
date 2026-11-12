"""Live events keep to their type, and only the event service broadcasts them."""

import asyncio
import hashlib
import json
from types import SimpleNamespace

from naas_abi_sdk.services.event import Event, EventService, LiveEvents

OWN = "https://example.org/ontology#OwnEvent"
OTHER = "https://example.org/ontology#OtherEvent"


def _msg(event_class):
    body = {"_uri": "urn:x"}
    if event_class is not None:
        body["_class_uri"] = event_class
    return SimpleNamespace(data=json.dumps(body).encode())


class Subscription:
    def __init__(self, *messages):
        self.queue = list(messages)

    async def next_msg(self, timeout=1.0):
        if not self.queue:
            raise asyncio.TimeoutError()
        return self.queue.pop(0)

    @property
    async def messages(self):
        for msg in list(self.queue):
            yield msg


def test_live_events_keep_to_the_subscribed_type():
    async def scenario():
        mixed = (
            _msg(OTHER),
            _msg(None),
            SimpleNamespace(data=b"not json"),
            _msg(OWN),
        )
        live = LiveEvents(Subscription(*mixed), OWN)
        first = await live.next_msg(timeout=1)
        assert json.loads(first.data)["_class_uri"] == OWN
        iterated = LiveEvents(Subscription(*mixed), OWN)
        kept = [json.loads(m.data)["_class_uri"] async for m in iterated.messages]
        assert kept == [OWN]

    asyncio.run(scenario())


class Bus:
    def __init__(self):
        self.published, self.subscribed = [], []

    async def publish(self, *args):
        self.published.append(args)

    async def subscribe(self, topic, routing_key):
        self.subscribed.append((topic, routing_key))
        return Subscription()


def test_a_published_event_keeps_its_broadcast_with_the_event_service():
    async def scenario():
        bus = Bus()
        service = EventService(client=None, bus=bus)
        requested = []

        async def request(operation, **values):
            requested.append(operation)
            return values

        service._request = request
        await service.publish(Event(event_type=OWN, payload={"a": 1}))
        assert requested == ["append"]
        assert bus.published == []  # the service broadcasts once it is appended
        live = await service.subscribe(OWN)
        assert isinstance(live, LiveEvents) and live.event_type == OWN
        topic = "evt." + hashlib.sha256(OWN.encode()).hexdigest()[:32]
        assert bus.subscribed == [(topic, "#")]

    asyncio.run(scenario())
