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


class Lyria3ProPreviewModel(ModelDefinition):
    CANONICAL_ID = "lyria-3-pro-preview"
    MODEL_ID = "google/lyria-3-pro-preview"
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
        context_window=1048576,
        name="Google: Lyria 3 Pro Preview",
        owner="google",
        description="Full-length songs are priced at $0.08 per song. Lyria 3 is Google's family of music generation models, available through the Gemini API. With Lyria 3, you can generate high-quality, 48kHz...",
        canonical_slug="google/lyria-3-pro-preview-20260330",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1774907286),
        pricing={'prompt': '0', 'completion': '0'},
        architecture={'modality': 'text+image->text+audio', 'input_modalities': ['text', 'image'], 'output_modalities': ['text', 'audio'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'response_format', 'seed', 'temperature', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Lyria3ProPreviewModel.model
