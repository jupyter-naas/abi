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


class ClaudeFable51BatchModel(ModelDefinition):
    CANONICAL_ID = "claude-fable-5.1:batch"
    MODEL_ID = "anthropic/claude-fable-5.1:batch"
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
        name="Anthropic: Claude Fable 5.1 (batch)",
        owner="anthropic",
        description="Claude Fable 5.1 improves on Claude Fable 5 across the board, with the biggest gains in agentic coding, long-running agentic workflows, and knowledge work: long code refactors, front-end and visual...",
        canonical_slug="anthropic/claude-fable-5.1-20260831",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1788285838),
        pricing={'prompt': '0.000005', 'completion': '0.000025', 'web_search': '0.01', 'input_cache_read': '0.000000125', 'input_cache_write': '0.00000625', 'input_cache_write_1h': '0.00001'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Claude', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'stop', 'structured_outputs', 'tool_choice', 'tools', 'verbosity'],
        default_parameters={},
    )


model: ChatModel = ClaudeFable51BatchModel.model
