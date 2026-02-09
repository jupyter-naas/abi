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
    
    def __init__(self, rabbitmq_url: str):
        self.__rabbitmq_url = rabbitmq_url
        self.__publish_connection = None
        self.__publish_channel = None

    def __enter__(self) -> "RabbitMQAdapter":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
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

    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        channel = self._ensure_publish_channel()
        try:
            # Create the exchange if it doesn't exist
            channel.exchange_declare(
                exchange=topic,
                exchange_type='topic',
                durable=True,
            )

            channel.basic_publish(
                exchange=topic,
                routing_key=routing_key,
                body=payload,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        except Exception as exc:
            self._close_publish_connection()
            raise ConnectionError("RabbitMQ publish failed") from exc
        
    def topic_consume(self, topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread:
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
                    exchange_type='topic',
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