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


class Qwen38MaxPrimeModel(ModelDefinition):
    CANONICAL_ID = "qwen3.8-max-prime"
    MODEL_ID = "qwen/qwen3.8-max-prime"
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
        context_window=1000000,
        name="Qwen: Qwen3.8 Max Prime",
        owner="qwen",
        description="Qwen3.8 Max Prime is a higher-throughput variant of Qwen3.8 Max from Alibaba's Qwen team, served as a separate SKU at a higher price point. It accepts text, image, and video...",
        canonical_slug="qwen/qwen3.8-max-prime-20260923",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1790191228),
        pricing={'prompt': '0.000004', 'completion': '0.000012', 'input_cache_read': '0.0000005'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Qwen38MaxPrimeModel.model
