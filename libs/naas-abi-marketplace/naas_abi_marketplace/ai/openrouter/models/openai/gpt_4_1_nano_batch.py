from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Gpt41NanoBatchModel(ModelDefinition):
    CANONICAL_ID = "gpt-4.1-nano:batch"
    MODEL_ID = "openai/gpt-4.1-nano:batch"
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
        context_window=1047576,
        name="OpenAI: GPT-4.1 Nano (batch)",
        owner="openai",
        description="For tasks that demand low latency, GPT‑4.1 nano is the fastest and cheapest model in the GPT-4.1 series. It delivers exceptional performance at a small size with its 1 million...",
        canonical_slug="openai/gpt-4.1-nano-2025-04-14",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1744651369),
        pricing={'prompt': '0.00000005', 'completion': '0.0000002', 'web_search': '0.01', 'input_cache_read': '0.0000000125'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['image', 'text', 'file'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 1047576, 'max_completion_tokens': 32768, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'response_format', 'seed', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gpt41NanoBatchModel.model
