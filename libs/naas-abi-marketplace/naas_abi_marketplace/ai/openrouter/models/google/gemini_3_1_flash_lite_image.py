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


class Gemini31FlashLiteImageModel(ModelDefinition):
    CANONICAL_ID = "gemini-3.1-flash-lite-image"
    MODEL_ID = "google/gemini-3.1-flash-lite-image"
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
        name="Google: Nano Banana 2 Lite (Gemini 3.1 Flash Lite Image)",
        owner="google",
        description="Nano Banana 2 Lite (Gemini 3.1 Flash Lite Image) is Google's fastest, most cost-efficient Gemini image model, built for high-velocity developer pipelines and rapid-fire visual exploration. It delivers text-to-image generation...",
        canonical_slug="google/gemini-3.1-flash-lite-image-20260630",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1782837225),
        pricing={'prompt': '0.00000025', 'completion': '0.0000015', 'image_output': '0.00003', 'web_search': '0.014'},
        architecture={'modality': 'text+image->text+image', 'input_modalities': ['image', 'text'], 'output_modalities': ['image', 'text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 65536, 'max_completion_tokens': 58982, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'temperature', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gemini31FlashLiteImageModel.model
