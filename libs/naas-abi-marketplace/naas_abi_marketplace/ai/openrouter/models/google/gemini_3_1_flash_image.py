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


class Gemini31FlashImageModel(ModelDefinition):
    CANONICAL_ID = "gemini-3.1-flash-image"
    MODEL_ID = "google/gemini-3.1-flash-image"
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
        name="Google: Nano Banana 2 (Gemini 3.1 Flash Image)",
        owner="google",
        description="Gemini 3.1 Flash Image, a.k.a. \"Nano Banana 2,\" is Google’s latest state of the art image generation and editing model, delivering Pro-level visual quality at Flash speed. It combines advanced...",
        canonical_slug="google/gemini-3.1-flash-image-20260528",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1781754065),
        pricing={'prompt': '0.0000005', 'completion': '0.000003', 'image_output': '0.00006', 'web_search': '0.014'},
        architecture={'modality': 'text+image->text+image', 'input_modalities': ['image', 'text'], 'output_modalities': ['image', 'text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'temperature', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gemini31FlashImageModel.model
