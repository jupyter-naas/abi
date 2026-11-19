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


class BodybuilderModel(ModelDefinition):
    CANONICAL_ID = "bodybuilder"
    MODEL_ID = "openrouter/bodybuilder"
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
        context_window=128000,
        name="Body Builder (beta)",
        owner="openrouter",
        description="Transform your natural language requests into structured OpenRouter API request objects. Describe what you want to accomplish with AI models, and Body Builder will construct the appropriate API calls. Example:...",
        canonical_slug="openrouter/bodybuilder",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1764903653),
        pricing={'prompt': '-1', 'completion': '-1'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Router', 'instruct_type': None},
        top_provider={'context_length': None, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=[],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = BodybuilderModel.model
