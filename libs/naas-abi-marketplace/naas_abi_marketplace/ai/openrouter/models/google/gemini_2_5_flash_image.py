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


class Gemini25FlashImageModel(ModelDefinition):
    CANONICAL_ID = "gemini-2.5-flash-image"
    MODEL_ID = "google/gemini-2.5-flash-image"
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
        context_window=32768,
        name="Google: Nano Banana (Gemini 2.5 Flash Image)",
        owner="google",
        description="Gemini 2.5 Flash Image, a.k.a. \"Nano Banana,\" is now generally available. It is a state of the art image generation model with contextual understanding. It is capable of image generation,...",
        canonical_slug="google/gemini-2.5-flash-image",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1759870431),
        pricing={'prompt': '0.0000003', 'completion': '0.0000025', 'image': '0.0000003', 'image_output': '0.00003', 'audio': '0.000001', 'input_audio_cache': '0.0000001', 'web_search': '0.014', 'internal_reasoning': '0.0000025', 'input_cache_read': '0.00000003', 'input_cache_write': '0.0000000833333333333333'},
        architecture={'modality': 'text+image->text+image', 'input_modalities': ['image', 'text'], 'output_modalities': ['image', 'text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 32768, 'max_completion_tokens': 8192, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Gemini25FlashImageModel.model
