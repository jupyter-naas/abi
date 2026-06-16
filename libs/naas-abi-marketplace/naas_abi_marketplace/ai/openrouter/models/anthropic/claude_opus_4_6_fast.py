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


class ClaudeOpus46FastModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_OPUS_4_6_FAST
    MODEL_ID = "anthropic/claude-opus-4.6-fast"
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
        name="Anthropic: Claude Opus 4.6 (Fast)",
        owner="anthropic",
        description="Fast-mode variant of [Opus 4.6](/anthropic/claude-opus-4.6) - identical capabilities with higher output speed at premium 6x pricing.\n\nLearn more in Anthropic's docs: https://platform.claude.com/docs/en/build-with-claude/fast-mode",
        canonical_slug="anthropic/claude-4.6-opus-fast-20260407",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1775592472),
        pricing={'prompt': '0.00003', 'completion': '0.00015', 'web_search': '0.01', 'input_cache_read': '0.000003', 'input_cache_write': '0.0000375'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Claude', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p', 'verbosity'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = ClaudeOpus46FastModel.model
