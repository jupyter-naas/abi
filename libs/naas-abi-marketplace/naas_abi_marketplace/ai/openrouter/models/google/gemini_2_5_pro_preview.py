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


class Gemini25ProPreviewModel(ModelDefinition):
    CANONICAL_ID = "gemini-2.5-pro-preview"
    MODEL_ID = "google/gemini-2.5-pro-preview"
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
        name="Google: Gemini 2.5 Pro Preview 06-05",
        owner="google",
        description="Gemini 2.5 Pro is Google’s state-of-the-art AI model designed for advanced reasoning, coding, mathematics, and scientific tasks. It employs “thinking” capabilities, enabling it to reason through responses with enhanced accuracy...",
        canonical_slug="google/gemini-2.5-pro-preview-06-05",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1749137257),
        pricing={'prompt': '0.00000125', 'completion': '0.00001', 'image': '0.00000125', 'audio': '0.00000125', 'input_audio_cache': '0.000000125', 'web_search': '0.014', 'internal_reasoning': '0.00001', 'input_cache_read': '0.000000125', 'input_cache_write': '0.000000375', 'overrides': [{'min_prompt_tokens': 200000, 'prompt': '0.0000025', 'completion': '0.000015', 'audio': '0.0000025', 'input_audio_cache': '0.00000025', 'input_cache_read': '0.00000025'}]},
        architecture={'modality': 'text+image+file+audio->text', 'input_modalities': ['file', 'image', 'text', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gemini25ProPreviewModel.model
