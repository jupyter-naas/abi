from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from threading import Thread


class IBusAdapter(ABC):
    """Bus port — two delivery models, pick the one that fits.

    **Pub/sub** (:meth:`publish` / :meth:`subscribe`)
        Every subscriber whose routing-key pattern matches a published
        message receives a copy. Live-only: a subscriber that joins after
        the publish does not see the message. No durability at the bus
        layer — callers that need replay keep their own log.

        Use for notifications and live event fanout (triple-store change
        events, EventService events, anything where "everyone listening
        should know about this").

        Use ``routing_key = "#"`` on the subscriber side for unconditional
        broadcast; otherwise the binding pattern follows AMQP topic syntax
        (``.`` separators, ``*`` for one segment, ``#`` for zero-or-more).

    **Work queue** (:meth:`enqueue` / :meth:`dequeue`)
        Each message is delivered to **exactly one** matching consumer.
        Durable: messages survive subscriber restart and are redelivered
        if a consumer crashes mid-processing.

        Use for jobs that must be processed once across a pool of workers
        (send this email, ingest this file, run this pipeline).
    """

    # ------------------------------------------------------------------
    # Pub/sub — fanout with routing-key matching, ephemeral.
    # ------------------------------------------------------------------

    @abstractmethod
    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        """Publish ``payload`` on ``topic`` with ``routing_key``.

        Every live subscriber on ``topic`` whose pattern matches
        ``routing_key`` receives a copy. No persistence: a subscriber
        connected after this call returns will not see the message.
        """
        raise NotImplementedError()

    def publish_many(
        self, topic: str, messages: Sequence[tuple[str, bytes]]
    ) -> None:
        """Publish a batch of ``(routing_key, payload)`` pairs on ``topic``.

        Subscribers observe exactly what they would have observed from the
        equivalent sequence of :meth:`publish` calls — this is a transport
        optimisation, not a delivery-semantics change. Adapters backed by a
        transactional store should override it to commit the whole batch in
        one round-trip; bulk producers (e.g. loading an ontology into the
        triple store) otherwise pay a full commit per message.

        The default implementation just loops, so adapters need not
        implement it.
        """
        for routing_key, payload in messages:
            self.publish(topic, routing_key, payload)

    @abstractmethod
    def subscribe(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        """Subscribe to messages on ``topic`` matching ``routing_key`` pattern.

        Each call registers an independent subscriber: two subscribers on
        the same ``(topic, routing_key)`` both receive every matching
        message — they don't compete. Use ``routing_key = "#"`` to receive
        every message on the topic.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------
    # Work queue — durable, exactly-one consumer per message.
    # ------------------------------------------------------------------

    @abstractmethod
    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        """Append a durable job to the work queue identified by ``topic``.

        The message survives until exactly one consumer ACKs it, including
        across restarts. If a consumer crashes before ACK, the message is
        redelivered.
        """
        raise NotImplementedError()

    @abstractmethod
    def dequeue(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        """Consume jobs from the work queue.

        Multiple ``dequeue`` calls on the same ``(topic, routing_key)``
        share a single durable queue and compete: each message goes to
        exactly one consumer. Use this when the message represents work
        to be done once, not an event to notify everyone about.
        """
        raise NotImplementedError()
