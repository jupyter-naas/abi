from langchain_core.language_models.chat_models import BaseChatModel
from typing import Any
from enum import Enum


class ModelType(Enum):
    CHAT = "chat"


class Model:
    model_id: str
    name: str
    description: str
    image: str
    owner: str
    model: Any
    model_type: ModelType

    def __init__(
        self,
        model_id: str,
        name: str,
        description: str,
        image: str,
        owner: str,
        model: Any,
    ):
        self.model_id = model_id
        self.name = name
        self.description = description
        self.image = image
        self.owner = owner
        self.model = model


class ChatModel(Model):
    model: BaseChatModel
    context_window: int
    model_type: ModelType = ModelType.CHAT

    def __init__(
        self,
        model_id: str,
        name: str,
        description: str,
        image: str,
        owner: str,
        model: BaseChatModel,
        context_window: int,
    ):
        super().__init__(model_id, name, description, image, owner, model)
        self.model_type = ModelType.CHAT
        self.context_window = context_window
