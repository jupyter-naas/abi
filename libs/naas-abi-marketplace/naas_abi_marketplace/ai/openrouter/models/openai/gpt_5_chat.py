from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Gpt5ChatModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_5_CHAT
    MODEL_ID = "openai/gpt-5-chat"
    PROVIDER = ModelProvider.OPENROUTER

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatOpenAI(
            model=MODEL_ID,
            temperature=0,
            timeout=120,
            max_retries=3,
            api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key),
            base_url=OPENROUTER_BASE_URL,
        ),
        context_window=128000,
        name="OpenAI: GPT-5 Chat",
        owner="openai",
        description="GPT-5 Chat is designed for advanced, natural, multimodal, and context-aware conversations for enterprise applications.",
        canonical_slug="openai/gpt-5-chat-2025-08-07",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1754587837),
        pricing={'prompt': '0.00000125', 'completion': '0.00001', 'web_search': '0.01', 'input_cache_read': '0.000000125'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['file', 'image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 16384, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'response_format', 'seed', 'structured_outputs'],
        default_parameters={},
    )


model: ChatModel = Gpt5ChatModel.model
