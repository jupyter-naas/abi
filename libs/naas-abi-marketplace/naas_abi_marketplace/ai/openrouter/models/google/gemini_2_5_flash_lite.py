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


class Gemini25FlashLiteModel(ModelDefinition):
    CANONICAL_ID = "gemini-2.5-flash-lite"
    MODEL_ID = "google/gemini-2.5-flash-lite"
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
        name="Google: Gemini 2.5 Flash Lite",
        owner="google",
        description="Gemini 2.5 Flash-Lite is a lightweight reasoning model in the Gemini 2.5 family, optimized for ultra-low latency and cost efficiency. It offers improved throughput, faster token generation, and better performance...",
        canonical_slug="google/gemini-2.5-flash-lite",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1753200276),
        pricing={'prompt': '0.0000001', 'completion': '0.0000004', 'image': '0.0000001', 'audio': '0.0000003', 'input_audio_cache': '0.00000003', 'web_search': '0.014', 'internal_reasoning': '0.0000004', 'input_cache_read': '0.00000001', 'input_cache_write': '0.0000000833333333333333'},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['text', 'image', 'file', 'audio', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65535, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Gemini25FlashLiteModel.model
