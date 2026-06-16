from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ClaudeSonnet46Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_SONNET_4_6
    MODEL_ID = "anthropic/claude-sonnet-4.6"
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
        context_window=1000000,
        name="Anthropic: Claude Sonnet 4.6",
        owner="anthropic",
        description="Sonnet 4.6 is Anthropic's most capable Sonnet-class model yet, with frontier performance across coding, agents, and professional work. It excels at iterative development, complex codebase navigation, end-to-end project management with...",
        canonical_slug="anthropic/claude-4.6-sonnet-20260217",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1771342990),
        pricing={'prompt': '0.000003', 'completion': '0.000015', 'web_search': '0.01', 'input_cache_read': '0.0000003', 'input_cache_write': '0.00000375'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Claude', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p', 'verbosity'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = ClaudeSonnet46Model.model
