import hashlib
from threading import Thread
from typing import Callable

import pika
from naas_abi_core.services.bus.BusPorts import IBusAdapter


class RabbitMQAdapter(IBusAdapter):
    __rabbitmq_url: str
    __publish_connection: pika.BlockingConnection
    __publish_channel: pika.adapters.blocking_connection.BlockingChannel
    
    def __init__(self, rabbitmq_url: str):
        self.__rabbitmq_url = rabbitmq_url
        self.__publish_connection = pika.BlockingConnection(
            pika.URLParameters(rabbitmq_url)
        )
        self.__publish_channel = self.__publish_connection.channel()

    @staticmethod
    def _durable_queue_name(topic: str, routing_key: str) -> str:
        digest = hashlib.sha256(f"{topic}:{routing_key}".encode("utf-8")).hexdigest()
        return f"naas-abi.{digest}"

    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        # Create the exchange if it doesn't exist
        self.__publish_channel.exchange_declare(
            exchange=topic,
            exchange_type='topic',
            durable=True,
        )
        
        self.__publish_channel.basic_publish(
            exchange=topic,
            routing_key=routing_key,
            body=payload,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        
    def topic_consume(self, topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread:
        def _consume_loop() -> None:
            connection = pika.BlockingConnection(
                pika.URLParameters(self.__rabbitmq_url)
            )
            channel = connection.channel()
            try:
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

                print(f"Consuming topic: {topic} -- {routing_key}")
                channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=_on_message,
                    auto_ack=False,
                )
                channel.start_consuming()
            finally:
                if channel.is_open:
                    channel.close()
                if connection.is_open:
                    connection.close()

        thread = Thread(target=_consume_loop, daemon=True)
        thread.start()
        return thread