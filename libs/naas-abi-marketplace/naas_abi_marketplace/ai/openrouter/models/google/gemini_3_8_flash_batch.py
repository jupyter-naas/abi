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


class Gemini38FlashBatchModel(ModelDefinition):
    CANONICAL_ID = "gemini-3.8-flash:batch"
    MODEL_ID = "google/gemini-3.8-flash:batch"
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
        name="Google: Gemini 3.8 Flash (batch)",
        owner="google",
        description="Gemini 3.8 Flash is Google's most intelligent Flash model with significant gains from 3.7 Flash across software engineering, agentic tasks, and multi-step reasoning.",
        canonical_slug="google/gemini-3.8-flash-20260902",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1788362056),
        pricing={'prompt': '0.000000375', 'completion': '0.000001875', 'image': '0.000000375', 'audio': '0.000000375', 'input_audio_cache': '0.0000000375', 'web_search': '0.014', 'internal_reasoning': '0.000001875', 'input_cache_read': '0.0000000375', 'input_cache_write': '0.0000000416666666666667'},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['text', 'image', 'video', 'file', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'stop', 'structured_outputs', 'tool_choice', 'tools'],
        default_parameters={},
    )


model: ChatModel = Gemini38FlashBatchModel.model
