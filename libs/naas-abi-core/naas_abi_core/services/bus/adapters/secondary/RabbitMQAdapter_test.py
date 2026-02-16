from unittest.mock import MagicMock

import pika
import pytest
from naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter import (
    RabbitMQAdapter,
)
from naas_abi_core.services.bus.tests.bus__secondary_adapter__generic_test import (
    GenericBusSecondaryAdapterTest,
)


class TestRabbitMQAdapter(GenericBusSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return RabbitMQAdapter


@pytest.fixture
def channel():
    channel = MagicMock()
    channel.is_open = True
    return channel


@pytest.fixture
def connection(channel):
    connection = MagicMock()
    connection.channel.return_value = channel
    connection.is_open = True
    return connection


@pytest.fixture
def adapter(monkeypatch, connection):
    monkeypatch.setattr(pika, "BlockingConnection", MagicMock(return_value=connection))
    return RabbitMQAdapter("amqp://localhost")


def _wait_for_thread(thread):
    thread.join(timeout=1)
    assert not thread.is_alive()


def test_init_is_lazy(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(pika, "BlockingConnection", connect)
    RabbitMQAdapter("amqp://localhost")
    connect.assert_not_called()


def test_topic_publish_connects_and_publishes(adapter, channel):
    adapter.topic_publish("topic", "routing.key", b"payload")

    channel.exchange_declare.assert_called_once_with(
        exchange="topic", exchange_type="topic", durable=True
    )
    args, kwargs = channel.basic_publish.call_args
    assert kwargs["exchange"] == "topic"
    assert kwargs["routing_key"] == "routing.key"
    assert kwargs["body"] == b"payload"
    assert kwargs["properties"].delivery_mode == 2


def test_topic_publish_error_closes_connection(monkeypatch, connection, channel):
    channel.exchange_declare.side_effect = RuntimeError("boom")
    monkeypatch.setattr(pika, "BlockingConnection", MagicMock(return_value=connection))
    adapter = RabbitMQAdapter("amqp://localhost")

    with pytest.raises(ConnectionError, match="RabbitMQ publish failed"):
        adapter.topic_publish("topic", "routing.key", b"payload")

    channel.close.assert_called_once()
    connection.close.assert_called_once()


def test_close_closes_publish_connection(monkeypatch, connection, channel):
    monkeypatch.setattr(pika, "BlockingConnection", MagicMock(return_value=connection))
    adapter = RabbitMQAdapter("amqp://localhost")
    adapter.topic_publish("topic", "routing.key", b"payload")

    adapter.close()

    channel.close.assert_called()
    connection.close.assert_called()


def test_topic_consume_declares_exchange_and_queue(adapter, channel):
    thread = adapter.topic_consume("topic", "routing.key", lambda _body: None)
    _wait_for_thread(thread)

    queue_name = RabbitMQAdapter._durable_queue_name("topic", "routing.key")
    channel.exchange_declare.assert_called_once_with(
        exchange="topic", exchange_type="topic", durable=True
    )
    channel.queue_declare.assert_called_once_with(
        queue=queue_name,
        durable=True,
        exclusive=False,
        auto_delete=False,
    )
    channel.queue_bind.assert_called_once_with(
        queue=queue_name, exchange="topic", routing_key="routing.key"
    )
    args, kwargs = channel.basic_consume.call_args
    assert kwargs["queue"] == queue_name
    assert kwargs["auto_ack"] is False
    channel.start_consuming.assert_called_once()


def test_topic_consume_acks_on_success(adapter, channel):
    callback = MagicMock()
    thread = adapter.topic_consume("topic", "routing.key", callback)
    _wait_for_thread(thread)

    on_message = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock()
    method.delivery_tag = "tag"

    on_message(channel, method, MagicMock(), b"payload")

    callback.assert_called_once_with(b"payload")
    channel.basic_ack.assert_called_once_with(delivery_tag="tag")


def test_topic_consume_nacks_on_failure(adapter, channel):
    def failing_callback(_body):
        raise ValueError("boom")

    thread = adapter.topic_consume("topic", "routing.key", failing_callback)
    _wait_for_thread(thread)

    on_message = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock()
    method.delivery_tag = "tag"

    with pytest.raises(ValueError, match="boom"):
        on_message(channel, method, MagicMock(), b"payload")

    channel.basic_nack.assert_called_once_with(delivery_tag="tag", requeue=True)
