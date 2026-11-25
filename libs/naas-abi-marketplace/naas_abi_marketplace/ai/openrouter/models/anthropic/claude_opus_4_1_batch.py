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


class ClaudeOpus41BatchModel(ModelDefinition):
    CANONICAL_ID = "claude-opus-4.1:batch"
    MODEL_ID = "anthropic/claude-opus-4.1:batch"
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
        context_window=200000,
        name="Anthropic: Claude Opus 4.1 (batch)",
        owner="anthropic",
        description="Claude Opus 4.1 is an updated version of Anthropic’s flagship model, offering improved performance in coding, reasoning, and agentic tasks. It achieves 74.5% on SWE-bench Verified and shows notable gains...",
        canonical_slug="anthropic/claude-4.1-opus-20250805",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1754411591),
        pricing={'prompt': '0.0000075', 'completion': '0.0000375', 'web_search': '0.01', 'input_cache_read': '0.00000075', 'input_cache_write': '0.000009375', 'input_cache_write_1h': '0.000015'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['image', 'text', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Claude', 'instruct_type': None},
        top_provider={'context_length': 200000, 'max_completion_tokens': 32000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = ClaudeOpus41BatchModel.model
