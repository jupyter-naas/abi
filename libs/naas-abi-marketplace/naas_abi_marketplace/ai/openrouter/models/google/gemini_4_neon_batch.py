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


class Gemini4NeonBatchModel(ModelDefinition):
    CANONICAL_ID = "gemini-4-neon:batch"
    MODEL_ID = "google/gemini-4-neon:batch"
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
        name="Google: Gemini 4 Neon (batch)",
        owner="google",
        description="Gemini 4 Neon is a fast, mid-priced model in the Gemini 4 family from Google, built for coding and agentic work. It is suited for repository and terminal coding, web...",
        canonical_slug="google/gemini-4-neon-20261118",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1795006977),
        pricing={'prompt': '0.0000015', 'completion': '0.0000075', 'image': '0.0000015', 'audio': '0.0000015', 'input_audio_cache': '0.000000075', 'web_search': '0.014', 'internal_reasoning': '0.0000075', 'input_cache_read': '0.000000075', 'input_cache_write': '0.0000000833333333333333'},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['audio', 'file', 'image', 'text', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gemini4NeonBatchModel.model
