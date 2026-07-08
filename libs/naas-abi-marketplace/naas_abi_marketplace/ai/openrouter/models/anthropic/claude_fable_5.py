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


class ClaudeFable5Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_FABLE_5
    MODEL_ID = "anthropic/claude-fable-5"
    PROVIDER = ModelProvider.OPENROUTER

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatOpenAI(
            model=MODEL_ID,
            temperature=0,
            timeout=120,
            max_retries=3,
            api_key=SecretStr(
                ABIModule.get_instance().configuration.openrouter_api_key
            ),
            base_url=OPENROUTER_BASE_URL,
        ),
        context_window=1000000,
        name="Fable 5",
        owner="anthropic",
        description="Claude Fable 5 is a Mythos-class model from Anthropic, built for autonomous knowledge work and coding. It supports text, image, and file inputs with text output, with reasoning support and...",
        canonical_slug="anthropic/claude-5-fable-20260609",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1781007515),
        pricing={
            "prompt": "0.00001",
            "completion": "0.00005",
            "web_search": "0.01",
            "input_cache_read": "0.000001",
            "input_cache_write": "0.0000125",
        },
        architecture={
            "modality": "text+image+file->text",
            "input_modalities": ["text", "image", "file"],
            "output_modalities": ["text"],
            "tokenizer": "Claude",
            "instruct_type": None,
        },
        top_provider={
            "context_length": 1000000,
            "max_completion_tokens": 128000,
            "is_moderated": True,
        },
        per_request_limits=None,
        supported_parameters=[
            "include_reasoning",
            "max_completion_tokens",
            "max_tokens",
            "reasoning",
            "response_format",
            "stop",
            "structured_outputs",
            "tool_choice",
            "tools",
            "verbosity",
        ],
        default_parameters={
            "temperature": None,
            "top_p": None,
            "top_k": None,
            "frequency_penalty": None,
            "presence_penalty": None,
            "repetition_penalty": None,
        },
    )


model: ChatModel = ClaudeFable5Model.model
