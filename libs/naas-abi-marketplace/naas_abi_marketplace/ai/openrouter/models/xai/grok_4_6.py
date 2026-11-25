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


class Grok46Model(ModelDefinition):
    CANONICAL_ID = "grok-4.6"
    MODEL_ID = "x-ai/grok-4.6"
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
        context_window=500000,
        name="SpaceXAI: Grok 4.6",
        owner="x-ai",
        description="Grok 4.6 is a model from SpaceXAI with frontier performance on coding, knowledge work, and STEM. It is succeeded by [Grok 4.7](/x-ai/grok-4.7).",
        canonical_slug="x-ai/grok-4.6-20260810",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1786548957),
        pricing={'prompt': '0.000002', 'completion': '0.000006', 'web_search': '0.005', 'input_cache_read': '0.0000005', 'overrides': [{'min_prompt_tokens': 200000, 'prompt': '0.000004', 'completion': '0.000012', 'input_cache_read': '0.000001'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Grok', 'instruct_type': None},
        top_provider={'context_length': 500000, 'max_completion_tokens': 450000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'logprobs', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Grok46Model.model
