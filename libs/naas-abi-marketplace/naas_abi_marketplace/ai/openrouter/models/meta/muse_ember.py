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


class MuseEmberModel(ModelDefinition):
    CANONICAL_ID = "muse-ember"
    MODEL_ID = "meta/muse-ember"
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
        name="Meta: Muse Ember",
        owner="meta",
        description="Muse Ember is the smallest and most efficient model from Meta that’s designed for complex reasoning execution and the work agents repeat all day: tool calls, coding agent subtasks, routing,...",
        canonical_slug="meta/muse-ember-20261109",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1794247648),
        pricing={'prompt': '0.0000001', 'completion': '0.0000005', 'web_search': '0.0025', 'input_cache_read': '0.000000004', 'input_cache_write': '0.000000125'},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['text', 'image', 'video', 'file', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MuseEmberModel.model
