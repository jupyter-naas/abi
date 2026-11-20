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


class Gemini31ProPreviewCustomtoolsModel(ModelDefinition):
    CANONICAL_ID = "gemini-3.1-pro-preview-customtools"
    MODEL_ID = "google/gemini-3.1-pro-preview-customtools"
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
        name="Google: Gemini 3.1 Pro Preview Custom Tools",
        owner="google",
        description="Gemini 3.1 Pro Preview Custom Tools is a variant of Gemini 3.1 Pro that improves tool selection behavior by preventing overuse of a general bash tool when more efficient third-party...",
        canonical_slug="google/gemini-3.1-pro-preview-customtools-20260219",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1772045923),
        pricing={'prompt': '0.000002', 'completion': '0.000012', 'image': '0.000002', 'audio': '0.000002', 'input_audio_cache': '0.0000002', 'web_search': '0.014', 'internal_reasoning': '0.000012', 'input_cache_read': '0.0000002', 'input_cache_write': '0.000000375', 'overrides': [{'min_prompt_tokens': 200000, 'prompt': '0.000004', 'completion': '0.000018', 'audio': '0.000004', 'input_audio_cache': '0.0000004', 'input_cache_read': '0.0000004'}]},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['text', 'audio', 'image', 'video', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Gemini31ProPreviewCustomtoolsModel.model
