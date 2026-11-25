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


class Ling30TinyModel(ModelDefinition):
    CANONICAL_ID = "ling-3.0-tiny"
    MODEL_ID = "inclusionai/ling-3.0-tiny"
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
        context_window=262144,
        name="inclusionAI: Ling 3.0 Tiny",
        owner="inclusionai",
        description="Ling 3.0 Tiny is a mixture-of-experts model from InclusionAI, with 1.3B active parameters out of 7.9B total. It is designed for responsive agents, instruction following, and multi-turn conversations, with switchable...",
        canonical_slug="inclusionai/ling-3.0-tiny-20260806",
        hugging_face_id="inclusionAI/Ling-3.0-tiny",
        created_at=datetime.fromtimestamp(1786034890),
        pricing={'prompt': '0.000000015', 'completion': '0.000000045', 'input_cache_read': '0.000000003'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 250000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': 20},
    )


model: ChatModel = Ling30TinyModel.model
