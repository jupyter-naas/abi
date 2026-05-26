import hashlib
from threading import Thread
from typing import Callable, Optional

import pika
from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.utils.Logger import logger


class RabbitMQAdapter(IBusAdapter):
    __rabbitmq_url: str
    __publish_connection: Optional[pika.BlockingConnection]
    __publish_channel: Optional[pika.adapters.blocking_connection.BlockingChannel]
    __declared_publish_exchanges: set[str]

    def __init__(self, rabbitmq_url: str):
        self.__rabbitmq_url = rabbitmq_url
        self.__publish_connection = None
        self.__publish_channel = None
        self.__declared_publish_exchanges = set()

    def __enter__(self) -> "RabbitMQAdapter":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self) -> None:
        self._close_publish_connection()

    def _close_publish_connection(self) -> None:
        if self.__publish_channel is not None:
            if self.__publish_channel.is_open:
                self.__publish_channel.close()
            self.__publish_channel = None
        if self.__publish_connection is not None:
            if self.__publish_connection.is_open:
                self.__publish_connection.close()
            self.__publish_connection = None
        self.__declared_publish_exchanges.clear()

    def _ensure_publish_channel(
        self,
    ) -> pika.adapters.blocking_connection.BlockingChannel:
        if self.__publish_channel is not None and self.__publish_channel.is_open:
            return self.__publish_channel

        self._close_publish_connection()
        connection = None
        try:
            connection = pika.BlockingConnection(
                pika.URLParameters(self.__rabbitmq_url)
            )
            channel = connection.channel()
        except Exception as exc:
            if connection is not None and connection.is_open:
                connection.close()
            raise ConnectionError("RabbitMQ connection failed") from exc

        self.__publish_connection = connection
        self.__publish_channel = channel
        return channel

    @staticmethod
    def _durable_queue_name(topic: str, routing_key: str) -> str:
        digest = hashlib.sha256(f"{topic}:{routing_key}".encode("utf-8")).hexdigest()
        return f"naas-abi.{digest}"

    def _do_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        """Internal: publish on the current channel, declaring exchange if needed."""
        channel = self._ensure_publish_channel()
        if topic not in self.__declared_publish_exchanges:
            channel.exchange_declare(
                exchange=topic,
                exchange_type="topic",
                durable=True,
            )
            self.__declared_publish_exchanges.add(topic)

        channel.basic_publish(
            exchange=topic,
            routing_key=routing_key,
            body=payload,
            properties=pika.BasicProperties(delivery_mode=2),
        )

    # ------------------------------------------------------------------
    # Work queue — durable topic exchange + shared durable queue.
    # All consumers on the same (topic, routing_key) share one queue and
    # RabbitMQ load-balances messages across them. Exactly-one delivery.
    # ------------------------------------------------------------------

    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        """Append *payload* to the work queue identified by *topic*/*routing_key*.

        Automatically reconnects once if the idle connection was closed by the
        broker (e.g. due to a missed heartbeat while the process was not
        actively publishing).
        """
        try:
            self._do_publish(topic, routing_key, payload)
        except Exception:
            # Connection was stale — drop it and retry with a fresh one.
            self._close_publish_connection()
            try:
                self._do_publish(topic, routing_key, payload)
            except Exception as exc:
                self._close_publish_connection()
                raise ConnectionError("RabbitMQ publish failed") from exc

    def dequeue(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        def _consume_loop() -> None:
            connection = None
            channel = None
            try:
                connection = pika.BlockingConnection(
                    pika.URLParameters(self.__rabbitmq_url)
                )
                channel = connection.channel()
                channel.exchange_declare(
                    exchange=topic,
                    exchange_type="topic",
                    durable=True,
                )

                queue_name = self._durable_queue_name(topic, routing_key)
                channel.queue_declare(
                    queue=queue_name,
                    durable=True,
                    exclusive=False,
                    auto_delete=False,
                )
                channel.queue_bind(
                    queue=queue_name,
                    exchange=topic,
                    routing_key=routing_key,
                )

                def _on_message(ch, method, properties, body):
                    try:
                        callback(body)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    except StopIteration:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        ch.stop_consuming()
                    except Exception:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                        raise

                logger.debug(f"Consuming topic: {topic} -- {routing_key}")
                channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=_on_message,
                    auto_ack=False,
                )
                channel.start_consuming()
            except (pika.exceptions.AMQPError, OSError) as exc:
                raise ConnectionError("RabbitMQ consume failed") from exc
            finally:
                if channel is not None and channel.is_open:
                    channel.close()
                if connection is not None and connection.is_open:
                    connection.close()

        thread = Thread(target=_consume_loop, daemon=True)
        thread.start()
        return thread

    # ------------------------------------------------------------------
    # Pub/sub — topic exchange + per-subscriber exclusive auto-delete queue.
    # Each subscribe call gets its OWN private queue bound to the topic
    # exchange with the supplied routing-key pattern. RabbitMQ then copies
    # every matching message to every subscriber's queue (fanout-like
    # semantics with routing-key filtering). Queues die with the consumer.
    # ------------------------------------------------------------------

    _PUBSUB_EXCHANGE_PREFIX = "naas-abi.pubsub."

    @staticmethod
    def _pubsub_exchange(topic: str) -> str:
        return f"{RabbitMQAdapter._PUBSUB_EXCHANGE_PREFIX}{topic}"

    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        channel = self._ensure_publish_channel()
        exchange = self._pubsub_exchange(topic)
        if exchange not in self.__declared_publish_exchanges:
            channel.exchange_declare(
                exchange=exchange,
                exchange_type="topic",
                durable=False,
                auto_delete=True,
            )
            self.__declared_publish_exchanges.add(exchange)
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=payload,
        )

    def subscribe(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        def _consume_loop() -> None:
            connection = None
            channel = None
            try:
                connection = pika.BlockingConnection(
                    pika.URLParameters(self.__rabbitmq_url)
                )
                channel = connection.channel()
                exchange = self._pubsub_exchange(topic)
                channel.exchange_declare(
                    exchange=exchange,
                    exchange_type="topic",
                    durable=False,
                    auto_delete=True,
                )
                # Server-generated unique name + exclusive + auto_delete →
                # one queue per subscriber that disappears when the channel
                # closes. No state survives a restart — Redis-style pub/sub.
                result = channel.queue_declare(
                    queue="",
                    exclusive=True,
                    auto_delete=True,
                    durable=False,
                )
                queue_name = result.method.queue
                channel.queue_bind(
                    queue=queue_name, exchange=exchange, routing_key=routing_key
                )

                def _on_message(ch, method, properties, body):
                    try:
                        callback(body)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    except StopIteration:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        ch.stop_consuming()
                    except Exception:
                        # Pub/sub is best-effort; ACK so a buggy subscriber
                        # doesn't redeliver the same message.
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        logger.exception(
                            f"RabbitMQAdapter: subscriber failed on {topic} -- {routing_key}"
                        )

                logger.debug(f"Subscribing: {topic} -- {routing_key}")
                channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=_on_message,
                    auto_ack=False,
                )
                channel.start_consuming()
            except (pika.exceptions.AMQPError, OSError) as exc:
                raise ConnectionError("RabbitMQ subscribe failed") from exc
            finally:
                if channel is not None and channel.is_open:
                    channel.close()
                if connection is not None and connection.is_open:
                    connection.close()

        thread = Thread(target=_consume_loop, daemon=True)
        thread.start()
        return thread
