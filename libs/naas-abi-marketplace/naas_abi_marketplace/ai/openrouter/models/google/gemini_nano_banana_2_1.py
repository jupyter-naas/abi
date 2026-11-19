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


class GeminiNanoBanana21Model(ModelDefinition):
    CANONICAL_ID = "gemini-nano-banana-2.1"
    MODEL_ID = "google/gemini-nano-banana-2.1"
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
        name="Google: Nano Banana 2.1",
        owner="google",
        description="Nano Banana 2.1 (Gemini Nano Banana 2.1) is Google's image generation and editing model on the Flash tier, succeeding Nano Banana 2 and Nano Banana Pro. It improves product recontextualization,...",
        canonical_slug="google/gemini-nano-banana-2.1-20261006",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1791300825),
        pricing={'prompt': '0.0000015', 'completion': '0.0000075', 'image_output': '0.00003', 'web_search': '0.014'},
        architecture={'modality': 'text+image->text+image', 'input_modalities': ['image', 'text'], 'output_modalities': ['image', 'text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 65536, 'max_completion_tokens': 58982, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = GeminiNanoBanana21Model.model
