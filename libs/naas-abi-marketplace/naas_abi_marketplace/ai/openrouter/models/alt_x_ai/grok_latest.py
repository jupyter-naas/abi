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


class GrokLatestModel(ModelDefinition):
    CANONICAL_ID = "grok-latest"
    MODEL_ID = "~x-ai/grok-latest"
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
        name="xAI: Grok Latest",
        owner="~x-ai",
        description="This model always redirects to the latest Grok model from xAI.",
        canonical_slug="~x-ai/grok-latest",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1783519360),
        pricing={'prompt': '0.000002', 'completion': '0.000006', 'web_search': '0.01', 'input_cache_read': '0.0000005', 'input_cache_write': '0', 'overrides': [{'min_prompt_tokens': 200000, 'prompt': '0.000004', 'completion': '0.000012', 'input_cache_read': '0.000001', 'input_cache_write': '0'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Router', 'instruct_type': None},
        top_provider={'context_length': 500000, 'max_completion_tokens': 450000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'logprobs', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 0.7, 'top_p': 0.95},
    )


model: ChatModel = GrokLatestModel.model
