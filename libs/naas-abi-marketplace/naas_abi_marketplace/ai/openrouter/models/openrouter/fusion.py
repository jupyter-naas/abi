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


class FusionModel(ModelDefinition):
    CANONICAL_ID = "fusion"
    MODEL_ID = "openrouter/fusion"
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
        name="OpenRouter: Fusion",
        owner="openrouter",
        description="Fusion turns your prompt into a small multi-model deliberation. A panel of expert models (see below) analyzes your prompt in parallel with web search and web fetch enabled, then a...",
        canonical_slug="openrouter/fusion",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1781371647),
        pricing={'prompt': '-1', 'completion': '-1'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Router', 'instruct_type': None},
        top_provider={'context_length': None, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=[],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = FusionModel.model
