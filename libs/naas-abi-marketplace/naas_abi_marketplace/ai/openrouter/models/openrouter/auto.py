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


class AutoModel(ModelDefinition):
    CANONICAL_ID = "auto"
    MODEL_ID = "openrouter/auto"
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
        name="Auto Router",
        owner="openrouter",
        description="Auto is OpenRouter’s flagship model router, built for general-purpose usage. It adapts to each request, choosing cost-optimal models and adjusting reasoning effort. It balances task difficulty, benchmark results, live prices,...",
        canonical_slug="openrouter/auto",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1793885889),
        pricing={'prompt': '-1', 'completion': '-1'},
        architecture={'modality': 'text+image+file+audio+video->text+image', 'input_modalities': ['text', 'image', 'audio', 'file', 'video'], 'output_modalities': ['text', 'image'], 'tokenizer': 'Router', 'instruct_type': None},
        top_provider={'context_length': None, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'prediction', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_a', 'top_k', 'top_logprobs', 'top_p', 'web_search_options'],
        default_parameters={},
    )


model: ChatModel = AutoModel.model
