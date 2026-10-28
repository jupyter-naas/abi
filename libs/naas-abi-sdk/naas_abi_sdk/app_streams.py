"""HTTP bodies streamed over NATS between Nexus and a module's app (abi.app.v1).

The reader pulls (``BodyPull``) and the holder answers one chunk per pull
(``BodyChunk``), so a body is never produced faster than it is consumed: a slow
module slows the browser's upload down, and a slow browser slows the module's
download, end to end. Memory holds about one chunk on each side.

Both directions use it: Nexus holds a request body and the module pulls it;
the module holds a response body and Nexus pulls it. A body inbox is a random
``_INBOX`` subject known only to the two parties.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from naas_abi_proto.app.v1 import app_pb2 as pb
from nats.errors import NoRespondersError
from nats.errors import TimeoutError as NATSTimeoutError

from naas_abi_sdk.broker_flush import flush_to_broker
from naas_abi_sdk.messages import reply, reply_allowed
from naas_abi_sdk.transport import RPCError

logger = logging.getLogger(__name__)

# A body up to this travels inline in HttpRequest/HttpResponse.
INLINE_BYTES = 256 * 1024
CHUNK_BYTES = 256 * 1024
# A pull with nothing new is answered empty after this: the reader asks again.
# It keeps an idle stream (server-sent events) alive through the pull timeout.
KEEPALIVE_SECONDS = 15.0
PULL_TIMEOUT_SECONDS = KEEPALIVE_SECONDS + 15.0
# A lost reply is asked for again, this many times in a row.
PULL_RETRIES = 3
# The holder gives up when nobody pulled for this long (the reader is gone).
IDLE_SECONDS = 60.0
# After the last chunk, a repeated pull is still answered for this long: past
# the reader's pull timeout, so the retry of a lost last reply finds it.
LINGER_SECONDS = PULL_TIMEOUT_SECONDS + 5.0

_END = object()


def chunk_bytes(max_payload: int) -> int:
    """A chunk that fits the broker's limit with room for the envelope."""
    return max(16 * 1024, min(CHUNK_BYTES, max_payload - 16 * 1024))


async def rechunk(pieces: AsyncIterable[bytes], size: int) -> AsyncIterator[bytes]:
    """``pieces`` regrouped into chunks of at most ``size`` bytes."""
    buffer = bytearray()
    async for piece in pieces:
        buffer += piece
        while len(buffer) >= size:
            yield bytes(buffer[:size])
            del buffer[:size]
    if buffer:
        yield bytes(buffer)


class BodyTooLarge(Exception):
    pass


class ReaderGone(Exception):
    """The body's reader cancelled or stopped pulling: stop producing."""


class BodySource:
    """Holds a body and answers pulls for it on its own inbox.

    The producer puts chunks with ``await put(data)`` (it waits while the
    previous chunk was not pulled yet) and ends with ``await finish()``, or
    ``await fail(code, message)``; ``abort(code, message)`` drops what was not
    pulled yet and ends with an error at once. ``gone`` is set when the reader
    cancelled or stopped pulling for IDLE_SECONDS; ``put`` then raises
    ReaderGone. After the last chunk the source answers a repeated pull for
    LINGER_SECONDS, then stops by itself: its owner need not wait for that.
    """

    def __init__(self, nc: Any, *, idle_seconds: float = IDLE_SECONDS) -> None:
        self.nc = nc
        self.inbox = nc.new_inbox()
        self.idle_seconds = idle_seconds
        self.queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=1)
        self.gone = asyncio.Event()
        self.done = asyncio.Event()
        self.pulled = False  # a chunk was delivered: the body is committed
        self._last: pb.BodyChunk | None = None
        self._subscription: Any = None
        self._watchdog: asyncio.Task | None = None
        # The pull being served: one at a time (a reader waits for each reply).
        self._serving: asyncio.Task | None = None
        self._last_pull = 0.0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._last_pull = asyncio.get_running_loop().time()
        self._subscription = await self.nc.subscribe(self.inbox, cb=self._on_pull)
        await flush_to_broker(self.nc)
        self._watchdog = asyncio.create_task(self._watch())

    async def put(self, data: bytes) -> None:
        if data:
            await self._put(data)

    async def finish(self) -> None:
        await self._put(_END)

    async def fail(self, code: str, message: str) -> None:
        await self._put(RPCError(code, message))

    def abort(self, code: str, message: str) -> None:
        """End the body with an error now, dropping the chunk not pulled yet:
        the reader's next pull gets the error instead of a clean end. A body
        whose end is already queued (all of it was taken) stays whole."""
        if self.done.is_set() or self.gone.is_set():
            return
        while not self.queue.empty():
            if self.queue.get_nowait() is _END:
                self.queue.put_nowait(_END)
                return
        self.queue.put_nowait(RPCError(code, message))

    async def settled(self) -> None:
        """Return once the reader took the body's end, or left."""
        done = asyncio.ensure_future(self.done.wait())
        gone = asyncio.ensure_future(self.gone.wait())
        try:
            await asyncio.wait({done, gone}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            done.cancel()
            gone.cancel()

    async def _put(self, item: Any) -> None:
        put = asyncio.ensure_future(self.queue.put(item))
        gone = asyncio.ensure_future(self.gone.wait())
        try:
            await asyncio.wait({put, gone}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            gone.cancel()
        if not put.done():
            put.cancel()
            raise ReaderGone()

    async def close(self) -> None:
        self.gone.set()
        if self._watchdog is not None:
            self._watchdog.cancel()
            await asyncio.gather(self._watchdog, return_exceptions=True)
            self._watchdog = None
        if self._serving is not None:
            self._serving.cancel()
            await asyncio.gather(self._serving, return_exceptions=True)
        if self._subscription is not None:
            with contextlib.suppress(Exception):
                await self._subscription.unsubscribe()
            self._subscription = None

    async def _watch(self) -> None:
        loop = asyncio.get_running_loop()
        while not self.gone.is_set():
            if self.done.is_set():
                await asyncio.sleep(LINGER_SECONDS)
                break
            if loop.time() - self._last_pull > self.idle_seconds:
                logger.info("Body reader gone: no pull for %.0f s", self.idle_seconds)
                break
            await asyncio.sleep(min(1.0, self.idle_seconds / 4))
        self.gone.set()
        if self._subscription is not None:
            with contextlib.suppress(Exception):
                await self._subscription.unsubscribe()
            self._subscription = None

    async def _on_pull(self, msg: Any) -> None:
        # A subscription runs one callback at a time: a pull waiting for the
        # next chunk must not hold back a cancel behind it (an idle stream).
        self._last_pull = asyncio.get_running_loop().time()
        try:
            pull = pb.BodyPull.FromString(msg.data)
        except Exception:  # noqa: BLE001 - a malformed pull gets an error
            pull = None
        if pull is not None and pull.cancel:
            self.gone.set()  # needs no answer
            return None
        if not reply_allowed(msg.reply):
            return None  # answered on an inbox only: the reply subject is the puller's
        if pull is None:
            return await self._answer(msg, _error("INVALID_ARGUMENT", "Bad pull"))
        if self._serving is not None and not self._serving.done():
            # A reader sends its next pull once answered: another one now is
            # out of turn, and is not queued (no backlog of waiting pulls).
            return await self._answer(
                msg, _error("INVALID_ARGUMENT", "A pull is already waiting")
            )
        self._serving = asyncio.create_task(self._serve(msg, pull))
        return None

    async def _serve(self, msg: Any, pull: pb.BodyPull) -> None:
        # Pulls are sequential; the lock keeps a re-sent pull in order.
        async with self._lock:
            self._last_pull = asyncio.get_running_loop().time()
            last = self._last
            if last is not None and pull.sequence == last.sequence:
                return await self._answer(msg, last)  # its reply was lost
            expected = 0 if last is None else last.sequence + 1
            if pull.sequence != expected or (last is not None and last.last):
                return await self._answer(
                    msg, _error("INVALID_ARGUMENT", "Pull out of sequence")
                )
            item = await self._next_item()
            if item is None:
                if not self.gone.is_set():
                    await self._answer(msg, pb.BodyChunk(sequence=pull.sequence))
                return None
            if isinstance(item, RPCError):
                chunk = _error(item.code, str(item))
                chunk.sequence, chunk.last = pull.sequence, True
                self.done.set()
            elif item is _END:
                chunk = pb.BodyChunk(sequence=pull.sequence, last=True)
                self.done.set()
            else:
                chunk = pb.BodyChunk(sequence=pull.sequence, data=item)
            self._last = chunk
            self.pulled = True
            await self._answer(msg, chunk)
            return None

    async def _next_item(self) -> Any:
        """The next chunk, or None after KEEPALIVE_SECONDS or once the reader left."""
        get = asyncio.ensure_future(self.queue.get())
        gone = asyncio.ensure_future(self.gone.wait())
        try:
            await asyncio.wait(
                {get, gone},
                timeout=KEEPALIVE_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            gone.cancel()
            if not get.done():
                get.cancel()
        if get.done() and not get.cancelled():
            return get.result()
        return None

    async def _answer(self, msg: Any, chunk: pb.BodyChunk) -> None:
        if msg.reply:
            try:
                await reply(msg, chunk.SerializeToString())
            except Exception:
                logger.debug("Could not answer a body pull", exc_info=True)


def _error(code: str, message: str) -> pb.BodyChunk:
    chunk = pb.BodyChunk()
    chunk.error.code, chunk.error.message = code, message
    return chunk


async def pull_body(
    nc: Any,
    inbox: str,
    *,
    max_bytes: int | None = None,
    timeout: float = PULL_TIMEOUT_SECONDS,
) -> AsyncIterator[bytes]:
    """The chunks of the body held at ``inbox``, pulled as they are iterated.

    Raises RPCError when the holder reports an error, ``BodyTooLarge`` past
    ``max_bytes`` (None: no limit), ``RPCError("DEADLINE_EXCEEDED")`` when the
    holder stopped answering and ``RPCError("UNAVAILABLE")`` when it is gone.
    Leaving the iteration early tells the holder, even when the reader is
    being cancelled.
    """
    sequence, total, finished = 0, 0, False
    try:
        while True:
            for attempt in range(PULL_RETRIES):
                try:
                    msg = await nc.request(
                        inbox,
                        pb.BodyPull(sequence=sequence).SerializeToString(),
                        timeout=timeout,
                    )
                    break
                except (NATSTimeoutError, asyncio.TimeoutError):
                    if attempt == PULL_RETRIES - 1:
                        raise RPCError(
                            "DEADLINE_EXCEEDED", "The body's holder stopped answering"
                        ) from None
                except NoRespondersError:
                    finished = True  # nobody to tell
                    raise RPCError("UNAVAILABLE", "The body's holder is gone") from None
            chunk = pb.BodyChunk.FromString(msg.data)
            if chunk.HasField("error") and chunk.error.code:
                finished = True
                raise RPCError(chunk.error.code, chunk.error.message)
            if chunk.sequence != sequence:
                raise RPCError("INVALID_ARGUMENT", "Body chunk out of sequence")
            if not chunk.data and not chunk.last:
                continue  # keepalive: nothing new yet
            total += len(chunk.data)
            if max_bytes is not None and total > max_bytes:
                raise BodyTooLarge(f"Body exceeds {max_bytes} bytes")
            if chunk.data:
                yield chunk.data
            if chunk.last:
                finished = True
                return
            sequence += 1
    finally:
        if not finished:
            await cancel_body(nc, inbox)


_cancels: set[asyncio.Task] = set()


async def cancel_body(nc: Any, inbox: str) -> None:
    """Tell the holder of the body at ``inbox`` that its reader left (as
    leaving ``pull_body`` early does, also before its first pull). The send
    runs in a task of its own: a reader leaves on cancellation (the browser
    went away), and the send must not be cancelled with it."""
    task = asyncio.ensure_future(_publish_cancel(nc, inbox))
    _cancels.add(task)
    task.add_done_callback(_cancels.discard)
    await asyncio.shield(task)


async def _publish_cancel(nc: Any, inbox: str) -> None:
    with contextlib.suppress(Exception):
        await nc.publish(inbox, pb.BodyPull(cancel=True).SerializeToString())
        await nc.flush(timeout=1)
