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


class Gpt41MiniModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_4_1_MINI
    MODEL_ID = "openai/gpt-4.1-mini"
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
        context_window=1047576,
        name="GPT-4.1 Mini",
        owner="openai",
        description="GPT-4.1 Mini is a mid-sized model delivering performance competitive with GPT-4o at substantially lower latency and cost. It retains a 1 million token context window and scores 45.1% on hard...",
        canonical_slug="openai/gpt-4.1-mini-2025-04-14",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1744651381),
        pricing={'prompt': '0.0000004', 'completion': '0.0000016', 'web_search': '0.01', 'input_cache_read': '0.0000001'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['image', 'text', 'file'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 1047576, 'max_completion_tokens': 32768, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['max_completion_tokens', 'max_tokens', 'response_format', 'seed', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gpt41MiniModel.model
