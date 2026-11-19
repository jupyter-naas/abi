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


class Moondream3PreviewModel(ModelDefinition):
    CANONICAL_ID = "moondream3-preview"
    MODEL_ID = "moondream/moondream3-preview"
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
        context_window=32000,
        name="Moondream: Moondream 3 Preview",
        owner="moondream",
        description="Moondream 3 Preview is a vision-language model from Moondream with 9B total parameters and 2B active (mixture-of-experts). It handles visual question answering, captioning, OCR, and visual reasoning over images, with...",
        canonical_slug="moondream/moondream3-preview-20261013",
        hugging_face_id="moondream/moondream3-preview",
        created_at=datetime.fromtimestamp(1792102385),
        pricing={'prompt': '0.0000003', 'completion': '0.0000025'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 32000, 'max_completion_tokens': 4096, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'temperature', 'top_p'],
        default_parameters={'temperature': 0.2, 'top_p': 0.9},
    )


model: ChatModel = Moondream3PreviewModel.model
