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


class O3Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.O3
    MODEL_ID = "openai/o3"
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
        context_window=200000,
        name="OpenAI: o3",
        owner="openai",
        description="o3 is a well-rounded and powerful model across domains. It sets a new standard for math, science, coding, and visual reasoning tasks. It also excels at technical writing and instruction-following....",
        canonical_slug="openai/o3-2025-04-16",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1744823457),
        pricing={'prompt': '0.000002', 'completion': '0.000008', 'web_search': '0.01', 'input_cache_read': '0.0000005'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['image', 'text', 'file'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 200000, 'max_completion_tokens': 100000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools'],
        default_parameters={},
    )


model: ChatModel = O3Model.model
