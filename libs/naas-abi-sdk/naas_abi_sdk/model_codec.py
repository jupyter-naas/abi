"""LangChain v1 message wire codec. Never deserialize Python constructors."""

import json
import math

from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

MESSAGE_TYPES = {
    "human",
    "ai",
    "system",
    "tool",
    "function",
    "chat",
    "remove",
    "HumanMessageChunk",
    "AIMessageChunk",
    "SystemMessageChunk",
    "ToolMessageChunk",
    "FunctionMessageChunk",
    "ChatMessageChunk",
}


def encode_json(value) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":")
    ).encode()


def decode_json(value: bytes, default=None):
    if not value:
        return default

    def invalid(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    def number(text):
        result = float(text)
        if not math.isfinite(result):
            raise ValueError("Non-finite JSON number")
        return result

    return json.loads(value, parse_constant=invalid, parse_float=number)


def encode_message(message: BaseMessage) -> pb.ChatMessage:
    value = message_to_dict(message)
    if value["type"] not in MESSAGE_TYPES:
        raise ValueError("Unsupported message type")
    return pb.ChatMessage(type=value["type"], data_json=encode_json(value["data"]))


def decode_message(message: pb.ChatMessage) -> BaseMessage:
    if message.type not in MESSAGE_TYPES:
        raise ValueError("Unsupported message type")
    data = decode_json(message.data_json)
    if not isinstance(data, dict) or data.get("type", message.type) != message.type:
        raise ValueError("Invalid message data")
    return messages_from_dict([{"type": message.type, "data": data}])[0]
