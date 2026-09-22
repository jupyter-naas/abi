import asyncio
import hashlib
from collections.abc import Callable
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import Self

import nats
import nats.errors
import nats.js.errors
from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.utils.Logger import logger
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg
from nats.js import JetStreamContext

_DEFAULT_TIMEOUT_SECONDS = 10.0


class NATSJetStreamAdapter(IBusAdapter):
    """NATS / JetStream implementation of :class:`IBusAdapter`.

    ``nats-py`` has no synchronous client, so this adapter bridges async
    NATS onto the synchronous port in two different shapes depending on
    which side of the port is being used:

    * :meth:`publish` / :meth:`enqueue` must return synchronously to an
      immediate caller. They share ONE persistent background thread running
      its own asyncio event loop (started lazily on first use) with a
      single NATS connection reused across calls. The synchronous method
      submits its coroutine with
      ``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)``
      and blocks until it completes or raises -- mirroring
      ``RabbitMQAdapter``'s reuse of one publish connection with
      reconnect-on-stale-connection retried once.
    * :meth:`subscribe` / :meth:`dequeue` each already return their own
      dedicated background ``Thread`` per the port contract. Each thread
      is async top-to-bottom: it creates its own fresh event loop and its
      own NATS connection and just runs the whole consume coroutine via
      ``loop.run_until_complete(...)`` for the thread's lifetime. No
      bridging is needed there.

    Mapping onto NATS/JetStream:

    * **Pub/sub** uses CORE NATS publish/subscribe (no JetStream, no
      durability) on subject ``f"{topic}.{routing_key}"``. Each
      :meth:`subscribe` call is its own independent NATS subscription (not
      a queue group), so two subscribers on the same pattern both receive
      every message -- matching the port's fanout semantics.
    * **Work queue** uses a JetStream stream per ``topic`` (subjects
      ``f"{topic}.>"``) plus a durable *pull* consumer whose name is
      deterministically derived from ``(topic, routing_key)`` (see
      :meth:`_durable_consumer_name`). Multiple :meth:`dequeue` calls on
      the same ``(topic, routing_key)`` therefore bind to the same durable
      consumer and JetStream load-balances pulls across them
      competing-consumer style: exactly-one delivery.
    """

    __nats_url: str
    __loop: asyncio.AbstractEventLoop | None
    __loop_thread: Thread | None
    __nc: NATSClient | None
    __js: JetStreamContext | None
    __declared_streams: set[str]
    __publish_lock: RLock

    def __init__(self, nats_url: str = "nats://127.0.0.1:4222") -> None:
        self.__nats_url = nats_url
        self.__loop = None
        self.__loop_thread = None
        self.__nc = None
        self.__js = None
        self.__declared_streams = set()
        # Serialize connection bookkeeping and synchronous submissions.
        self.__publish_lock = RLock()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self) -> None:
        with self.__publish_lock:
            self._close_publish_connection()
            self._stop_loop()

    # ------------------------------------------------------------------
    # Persistent background event loop backing publish/enqueue.
    # ------------------------------------------------------------------

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self.__loop is not None and self.__loop.is_running():
            return self.__loop

        ready = ThreadingEvent()
        holder: dict[str, asyncio.AbstractEventLoop] = {}

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            holder["loop"] = loop
            loop.call_soon(ready.set)
            loop.run_forever()
            loop.close()

        thread = Thread(
            target=_run, daemon=True, name="nats-jetstream-adapter-publish-loop"
        )
        thread.start()
        ready.wait()
        self.__loop = holder["loop"]
        self.__loop_thread = thread
        return self.__loop

    def _run_coro(self, coro, timeout: float = _DEFAULT_TIMEOUT_SECONDS):
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise

    def _stop_loop(self) -> None:
        loop = self.__loop
        thread = self.__loop_thread
        self.__loop = None
        self.__loop_thread = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5.0)

    async def _ensure_connection_async(self) -> tuple[NATSClient, JetStreamContext]:
        if self.__nc is not None and not self.__nc.is_closed:
            assert self.__js is not None
            return self.__nc, self.__js

        nc = await nats.connect(self.__nats_url, pending_size=0)
        js = nc.jetstream()
        self.__nc = nc
        self.__js = js
        self.__declared_streams.clear()
        return nc, js

    def _close_publish_connection(self) -> None:
        nc = self.__nc
        self.__nc = None
        self.__js = None
        self.__declared_streams.clear()
        if nc is not None and self.__loop is not None and self.__loop.is_running():
            try:
                self._run_coro(nc.close(), timeout=5.0)
            except Exception:  # noqa: BLE001
                # Best-effort close of a connection we're discarding anyway
                # (already stale, or being replaced by a fresh reconnect) --
                # nothing meaningful to do with the error, but worth a trace
                # for anyone debugging connection churn.
                logger.opt(exception=True).debug(
                    "NATSJetStreamAdapter: error closing stale connection"
                )

    # ------------------------------------------------------------------
    # Naming helpers.
    # ------------------------------------------------------------------

    @staticmethod
    def _subject(topic: str, routing_key: str) -> str:
        return f"{topic}.{routing_key}"

    @staticmethod
    def _stream_name(topic: str) -> str:
        # NATS stream names may not contain '.', '*', '>', '/', '\\' or
        # whitespace, so `topic` (which routinely contains dots, e.g.
        # "evt.x") can't be used verbatim. Hash it instead -- same idea as
        # RabbitMQAdapter._durable_queue_name, hex digest is always safe.
        digest = hashlib.sha256(topic.encode()).hexdigest()
        return f"naas-abi-{digest}"

    @staticmethod
    def _durable_consumer_name(topic: str, routing_key: str) -> str:
        # Deterministic from (topic, routing_key) so every dequeue() call on
        # the same pair binds to the same durable consumer and JetStream
        # load-balances pulls across them (competing consumers).
        digest = hashlib.sha256(f"{topic}:{routing_key}".encode()).hexdigest()
        return f"naas-abi-{digest}"

    @staticmethod
    def _to_nats_pattern(routing_key: str) -> str:
        """Translate an AMQP-style routing-key pattern to a NATS subject pattern.

        ``.`` stays the segment separator and ``*`` already means "exactly
        one segment" under both syntaxes, so only ``#`` needs translating.
        NATS' closest equivalent is ``>``, but ``>`` only matches
        **one-or-more** trailing tokens (not zero-or-more) and is only legal
        as the final token of a subject. Every caller in this codebase uses
        ``#`` as the whole pattern or as a trailing segment (see
        ``EventService.subscribe`` and the ``PythonQueueAdapter`` tests), so
        that's the only shape translated here.

        Gap versus AMQP, documented rather than worked around: AMQP's ``#``
        can also match *zero* segments -- a publish on the bare topic with
        no routing-key segments at all would still match a ``#`` binding
        under RabbitMQ. NATS has no "zero-or-more" wildcard: a
        ``topic.>`` subscription requires at least one more token, so the
        equivalent bare-topic publish would NOT match it. No caller in this
        codebase currently publishes with an empty routing key (EventService
        always uses the event id; every adapter test uses a non-empty key),
        so this is intentionally left undressed rather than over-engineered.
        """
        if routing_key == "#":
            return ">"
        parts = routing_key.split(".")
        if "#" in parts[:-1]:
            logger.warning(
                f"NATSJetStreamAdapter: routing-key pattern {routing_key!r} uses "
                "'#' outside the trailing position; NATS only supports a "
                "trailing '>' wildcard, so that segment will be matched "
                "literally instead of as a wildcard."
            )
        if parts[-1] == "#":
            parts[-1] = ">"
        return ".".join(parts)

    async def _ensure_stream_async(self, js: JetStreamContext, topic: str) -> str:
        stream_name = self._stream_name(topic)
        if stream_name in self.__declared_streams:
            return stream_name

        try:
            await js.add_stream(name=stream_name, subjects=[f"{topic}.>"])
        except nats.js.errors.BadRequestError as exc:
            # Tolerate a concurrent creator winning the race ("stream name
            # already in use"). Confirm the stream actually exists before
            # swallowing, so a genuine conflict (e.g. an unrelated stream
            # whose subjects happen to overlap) still surfaces.
            try:
                await js.stream_info(stream_name)
            except Exception:  # noqa: BLE001 - any failure here should surface the original conflict, not itself
                raise exc from None

        self.__declared_streams.add(stream_name)
        return stream_name

    # ------------------------------------------------------------------
    # Pub/sub -- core NATS, ephemeral, per-subscriber fanout.
    # ------------------------------------------------------------------

    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        """Publish once; a failed flush does not prove the message was not sent."""
        subject = self._subject(topic, routing_key)
        with self.__publish_lock:
            self._run_coro(self._do_publish_async(subject, payload))

    async def _do_publish_async(self, subject: str, payload: bytes) -> None:
        nc, _js = await self._ensure_connection_async()
        await nc.publish(subject, payload)
        # Core NATS publish only buffers the frame; flush so the message is
        # genuinely on the wire by the time the synchronous caller gets
        # control back, matching the "block until it completes" contract of
        # the sync bridge.
        await nc.flush()

    def subscribe(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        def _consume_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self._subscribe_forever(topic, routing_key, callback)
                )
            finally:
                loop.close()

        thread = Thread(target=_consume_loop, daemon=True)
        thread.start()
        return thread

    async def _subscribe_forever(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> None:
        nc = await nats.connect(self.__nats_url)
        subject = self._subject(topic, self._to_nats_pattern(routing_key))
        stop_event = asyncio.Event()

        async def _on_message(msg: Msg) -> None:
            try:
                callback(msg.data)
            except StopIteration:
                stop_event.set()
            except Exception:  # noqa: BLE001
                # Core NATS pub/sub has no ack/nack, so there's nothing to
                # redeliver even if we wanted to -- best-effort: log and
                # swallow so one bad subscriber can't wedge the loop. Same
                # spirit as RabbitMQAdapter's ack-always-even-on-failure.
                logger.exception(
                    f"NATSJetStreamAdapter: subscriber failed on {topic} -- {routing_key}"
                )

        logger.debug(f"Subscribing: {topic} -- {routing_key}")
        sub = await nc.subscribe(subject, cb=_on_message)
        try:
            await stop_event.wait()
        finally:
            try:
                await sub.unsubscribe()
            except Exception:  # noqa: BLE001
                # Best-effort on the way out -- the connection is closing
                # right after this regardless, but worth a trace.
                logger.opt(exception=True).debug(
                    "NATSJetStreamAdapter: error unsubscribing during shutdown"
                )
            await nc.close()

    # ------------------------------------------------------------------
    # Work queue -- JetStream stream + durable pull consumer per
    # (topic, routing_key). Exactly-one delivery, durable across restarts.
    # ------------------------------------------------------------------

    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        """Append once; a lost acknowledgement can hide a successful durable write."""
        subject = self._subject(topic, routing_key)
        with self.__publish_lock:
            self._run_coro(self._do_enqueue_async(topic, subject, payload))

    async def _do_enqueue_async(self, topic: str, subject: str, payload: bytes) -> None:
        _nc, js = await self._ensure_connection_async()
        stream_name = await self._ensure_stream_async(js, topic)
        await js.publish(subject, payload, stream=stream_name)

    def dequeue(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        def _consume_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self._dequeue_forever(topic, routing_key, callback)
                )
            finally:
                loop.close()

        thread = Thread(target=_consume_loop, daemon=True)
        thread.start()
        return thread

    async def _dequeue_forever(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> None:
        nc = await nats.connect(self.__nats_url)
        try:
            js = nc.jetstream()
            stream_name = await self._ensure_stream_async(js, topic)
            durable_name = self._durable_consumer_name(topic, routing_key)
            filter_subject = self._subject(topic, self._to_nats_pattern(routing_key))

            logger.debug(f"Consuming topic: {topic} -- {routing_key}")
            sub = await js.pull_subscribe(
                filter_subject, durable=durable_name, stream=stream_name
            )
            while True:
                try:
                    msgs = await sub.fetch(1, timeout=1.0)
                except nats.errors.TimeoutError:
                    # No message within this poll window -- keep polling.
                    continue

                for msg in msgs:
                    try:
                        callback(msg.data)
                        await msg.ack()
                    except StopIteration:
                        await msg.ack()
                        return
                    except Exception:
                        await msg.nak()
                        raise
        finally:
            await nc.close()
