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


class Gemini25FlashModel(ModelDefinition):
    CANONICAL_ID = "gemini-2.5-flash"
    MODEL_ID = "google/gemini-2.5-flash"
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
        name="Google: Gemini 2.5 Flash",
        owner="google",
        description="Gemini 2.5 Flash is Google's state-of-the-art workhorse model, specifically designed for advanced reasoning, coding, mathematics, and scientific tasks. It includes built-in \"thinking\" capabilities, enabling it to provide responses with greater...",
        canonical_slug="google/gemini-2.5-flash",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1750172488),
        pricing={'prompt': '0.0000003', 'completion': '0.0000025', 'image': '0.0000003', 'audio': '0.000001', 'input_audio_cache': '0.0000001', 'web_search': '0.014', 'internal_reasoning': '0.0000025', 'input_cache_read': '0.00000003', 'input_cache_write': '0.0000000833333333333333'},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['file', 'image', 'text', 'audio', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65535, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Gemini25FlashModel.model
