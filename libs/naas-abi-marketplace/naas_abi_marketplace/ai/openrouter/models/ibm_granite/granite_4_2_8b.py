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


class Granite428bModel(ModelDefinition):
    CANONICAL_ID = "granite-4.2-8b"
    MODEL_ID = "ibm-granite/granite-4.2-8b"
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
        context_window=131072,
        name="IBM: Granite 4.2 8B",
        owner="ibm-granite",
        description="Granite 4.2 8B is a dense reasoning model from IBM. It is suited for mathematics, code generation, multilingual dialogue, and agentic workflows that need multi-step reasoning. It supports full, low-effort,...",
        canonical_slug="ibm-granite/granite-4.2-8b-20260831",
        hugging_face_id="ibm-granite/granite-4.2-8b",
        created_at=datetime.fromtimestamp(1788206780),
        pricing={'prompt': '0.00000006', 'completion': '0.00000015', 'input_cache_read': '0.000000015'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 117964, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95},
    )


model: ChatModel = Granite428bModel.model
