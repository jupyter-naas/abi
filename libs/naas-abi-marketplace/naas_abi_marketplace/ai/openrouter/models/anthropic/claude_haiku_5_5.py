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


class ClaudeHaiku55Model(ModelDefinition):
    CANONICAL_ID = "claude-haiku-5.5"
    MODEL_ID = "anthropic/claude-haiku-5.5"
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
        name="Anthropic: Claude Haiku 5.5",
        owner="anthropic",
        description="Claude Haiku 5.5 is Anthropic's small, fast model for high-volume, cost-sensitive work such as summarization, subagents, and browser use. It succeeds Claude Haiku 4.5 with stronger coding, computer use, and...",
        canonical_slug="anthropic/claude-haiku-5.5-20261007",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1791397883),
        pricing={'prompt': '0.0000001', 'completion': '0.0000005', 'web_search': '0.01', 'input_cache_read': '0.00000001', 'input_cache_write': '0.000000125', 'input_cache_write_1h': '0.0000002', 'overrides': [{'min_prompt_tokens': 100000, 'prompt': '0.0000005', 'completion': '0.0000025', 'input_cache_read': '0.00000005', 'input_cache_write': '0.000000625', 'input_cache_write_1h': '0.000001'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Claude', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'stop', 'structured_outputs', 'tool_choice', 'tools', 'verbosity'],
        default_parameters={},
    )


model: ChatModel = ClaudeHaiku55Model.model
