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


class Gemini3ProImagePreviewModel(ModelDefinition):
    CANONICAL_ID = "gemini-3-pro-image-preview"
    MODEL_ID = "google/gemini-3-pro-image-preview"
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
        context_window=65536,
        name="Google: Nano Banana Pro (Gemini 3 Pro Image Preview)",
        owner="google",
        description="Nano Banana Pro is Google’s most advanced image-generation and editing model, built on Gemini 3 Pro. It extends the original Nano Banana with significantly improved multimodal reasoning, real-world grounding, and...",
        canonical_slug="google/gemini-3-pro-image-preview-20251120",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1763653797),
        pricing={'prompt': '0.000002', 'completion': '0.000012', 'image': '0.000002', 'image_output': '0.00012', 'audio': '0.000002', 'input_audio_cache': '0.0000002', 'web_search': '0.014', 'internal_reasoning': '0.000012', 'input_cache_read': '0.0000002', 'input_cache_write': '0.000000375'},
        architecture={'modality': 'text+image->text+image', 'input_modalities': ['image', 'text'], 'output_modalities': ['image', 'text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 65536, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Gemini3ProImagePreviewModel.model
