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


class Qwen3CoderNextModel(ModelDefinition):
    CANONICAL_ID = "qwen3-coder-next"
    MODEL_ID = "qwen/qwen3-coder-next"
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
        name="Qwen: Qwen3 Coder Next",
        owner="qwen",
        description="Qwen3-Coder-Next is an open-weight causal language model optimized for coding agents and local development workflows. It uses a sparse MoE design with 80B total parameters and only 3B activated per...",
        canonical_slug="qwen/qwen3-coder-next-2025-02-03",
        hugging_face_id="Qwen/Qwen3-Coder-Next",
        created_at=datetime.fromtimestamp(1770164101),
        pricing={'prompt': '0.00000012', 'completion': '0.0000008', 'input_cache_read': '0.00000007'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'frequency_penalty': None},
    )


model: ChatModel = Qwen3CoderNextModel.model
