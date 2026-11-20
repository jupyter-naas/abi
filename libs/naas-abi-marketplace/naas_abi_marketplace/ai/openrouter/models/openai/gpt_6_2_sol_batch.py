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


class Gpt62SolBatchModel(ModelDefinition):
    CANONICAL_ID = "gpt-6.2-sol:batch"
    MODEL_ID = "openai/gpt-6.2-sol:batch"
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
        context_window=1050000,
        name="OpenAI: GPT-6.2 Sol (batch)",
        owner="openai",
        description="GPT-6.2 Sol is an upgrade to GPT-6.1 Sol from OpenAI, positioned below the flagship GPT-6.2 Astra in the GPT-6.2 series. It is an efficient, versatile model for everyday work, suited...",
        canonical_slug="openai/gpt-6.2-sol-20261117",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1794938371),
        pricing={'prompt': '0.000001', 'completion': '0.000005', 'web_search': '0.01', 'input_cache_read': '0.00000005', 'input_cache_write': '0.00000125', 'overrides': [{'min_prompt_tokens': 272000, 'prompt': '0.000002', 'completion': '0.0000075', 'input_cache_read': '0.0000001', 'input_cache_write': '0.0000025'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['file', 'image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 1050000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools', 'verbosity'],
        default_parameters={},
    )


model: ChatModel = Gpt62SolBatchModel.model
