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


class Ling30FlashModel(ModelDefinition):
    CANONICAL_ID = "ling-3.0-flash"
    MODEL_ID = "inclusionai/ling-3.0-flash"
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
        name="inclusionAI: Ling 3.0 Flash",
        owner="inclusionai",
        description="*Ling-3.0-flash* is a *124B-parameter Mixture-of-Experts (MoE) model*, with approximately *5.1B parameters activated per token*. The model is designed with *token efficiency and production-scale agentic inference* as key priorities, enabling developers...",
        canonical_slug="inclusionai/ling-3.0-flash-20260723",
        hugging_face_id="inclusionAI/Ling-3.0-flash",
        created_at=datetime.fromtimestamp(1784818580),
        pricing={'prompt': '0.000000021', 'completion': '0.000000063', 'input_cache_read': '0.0000000042'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Ling30FlashModel.model
