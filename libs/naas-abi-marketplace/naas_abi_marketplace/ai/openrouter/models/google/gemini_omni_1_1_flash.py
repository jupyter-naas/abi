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


class GeminiOmni11FlashModel(ModelDefinition):
    CANONICAL_ID = "gemini-omni-1.1-flash"
    MODEL_ID = "google/gemini-omni-1.1-flash"
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
        name="Google: Gemini Omni 1.1 Flash",
        owner="google",
        description="Gemini Omni 1.1 Flash is Google's native multimodal video generation and editing model, the generally available successor to Gemini Omni Flash Preview. It is suited for text-to-video, image-to-video, first and...",
        canonical_slug="google/gemini-omni-1.1-flash-20260911",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1793825668),
        pricing={'prompt': '0.0000015', 'completion': '0.000009', 'web_search': '0.014'},
        architecture={'modality': 'text+image+video->text+video', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text', 'video'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'seed', 'temperature', 'top_p'],
        default_parameters={},
    )


model: ChatModel = GeminiOmni11FlashModel.model
