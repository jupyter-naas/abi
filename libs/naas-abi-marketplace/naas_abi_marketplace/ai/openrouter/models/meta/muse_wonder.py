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


class MuseWonderModel(ModelDefinition):
    CANONICAL_ID = "muse-wonder"
    MODEL_ID = "meta/muse-wonder"
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
        name="Meta: Muse Wonder",
        owner="meta",
        description="Muse Wonder is a frontier reasoning model from Meta, designed for complex personal and professional agentic tasks. It accepts text, images, video, audio, and PDF documents and returns text, with...",
        canonical_slug="meta/muse-wonder-20261012",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1791807945),
        pricing={'prompt': '0.000004', 'completion': '0.00002', 'web_search': '0.01', 'input_cache_read': '0.0000002'},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['text', 'image', 'video', 'file', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MuseWonderModel.model
