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


class Grok420Model(ModelDefinition):
    CANONICAL_ID = "grok-4.20"
    MODEL_ID = "x-ai/grok-4.20"
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
        context_window=2000000,
        name="SpaceXAI: Grok 4.20",
        owner="x-ai",
        description="Grok 4.20 is a reasoning model from SpaceXAI with industry-leading speed and agentic tool calling capabilities. It combines the lowest hallucination rate on the market with strict prompt adherance, delivering...",
        canonical_slug="x-ai/grok-4.20-20260309",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1774979019),
        pricing={'prompt': '0.00000125', 'completion': '0.0000025', 'web_search': '0.005', 'input_cache_read': '0.0000002', 'overrides': [{'min_prompt_tokens': 200000, 'prompt': '0.0000025', 'completion': '0.000005', 'input_cache_read': '0.0000004'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Grok', 'instruct_type': None},
        top_provider={'context_length': 2000000, 'max_completion_tokens': 1800000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'logprobs', 'max_tokens', 'reasoning', 'response_format', 'seed', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Grok420Model.model
