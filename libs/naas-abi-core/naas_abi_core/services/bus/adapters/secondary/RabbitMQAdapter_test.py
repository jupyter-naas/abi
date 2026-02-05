from unittest.mock import MagicMock

import pika
import pytest
from naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter import \
    RabbitMQAdapter
from naas_abi_core.services.bus.tests.bus__secondary_adapter__generic_test import \
    GenericBusSecondaryAdapterTest


class TestRabbitMQAdapter(GenericBusSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return RabbitMQAdapter


@pytest.fixture
def channel():
    channel = MagicMock()
    queue_result = MagicMock()
    queue_result.method.queue = "queue"
    channel.queue_declare.return_value = queue_result
    return channel


@pytest.fixture
def adapter(monkeypatch, channel):
    connection = MagicMock()
    connection.channel.return_value = channel
    monkeypatch.setattr(pika, "BlockingConnection", MagicMock(return_value=connection))
    return RabbitMQAdapter("localhost")


def test_topic_consume_declares_exchange_and_queue(adapter, channel):
    adapter.topic_consume("topic", lambda _body: None)

    channel.exchange_declare.assert_called_once_with(
        exchange="topic", exchange_type="topic"
    )
    channel.queue_declare.assert_called_once_with(queue="", exclusive=True)
    channel.queue_bind.assert_called_once_with(
        queue="queue", exchange="topic", routing_key="topic"
    )
    channel.basic_consume.assert_called_once()
    channel.start_consuming.assert_called_once()


def test_topic_consume_acks_on_success(adapter, channel):
    callback = MagicMock()
    adapter.topic_consume("topic", callback)

    on_message = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock()
    method.delivery_tag = "tag"

    on_message(channel, method, MagicMock(), b"payload")

    callback.assert_called_once_with(b"payload")
    channel.basic_ack.assert_called_once_with(delivery_tag="tag")


def test_topic_consume_nacks_on_failure(adapter, channel):
    def failing_callback(_body):
        raise ValueError("boom")

    adapter.topic_consume("topic", failing_callback)

    on_message = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock()
    method.delivery_tag = "tag"

    with pytest.raises(ValueError, match="boom"):
        on_message(channel, method, MagicMock(), b"payload")

    channel.basic_nack.assert_called_once_with(delivery_tag="tag", requeue=True)
