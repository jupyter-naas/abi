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


class Gemini31FlashImagePreviewModel(ModelDefinition):
    CANONICAL_ID = "gemini-3.1-flash-image-preview"
    MODEL_ID = "google/gemini-3.1-flash-image-preview"
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
        name="Google: Nano Banana 2 (Gemini 3.1 Flash Image Preview)",
        owner="google",
        description="Gemini 3.1 Flash Image Preview, a.k.a. \"Nano Banana 2,\" is Google’s latest state of the art image generation and editing model, delivering Pro-level visual quality at Flash speed. It combines...",
        canonical_slug="google/gemini-3.1-flash-image-preview-20260226",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1772119558),
        pricing={'prompt': '0.0000005', 'completion': '0.000003', 'image_output': '0.00006', 'web_search': '0.014'},
        architecture={'modality': 'text+image->text+image', 'input_modalities': ['image', 'text'], 'output_modalities': ['image', 'text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 65536, 'max_completion_tokens': 58982, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'temperature', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Gemini31FlashImagePreviewModel.model
