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


class Gpt52CodexModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_5_2_CODEX
    MODEL_ID = "openai/gpt-5.2-codex"
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
        context_window=400000,
        name="OpenAI: GPT-5.2-Codex",
        owner="openai",
        description="GPT-5.2-Codex is an upgraded version of GPT-5.1-Codex optimized for software engineering and coding workflows. It is designed for both interactive development sessions and long, independent execution of complex engineering tasks....",
        canonical_slug="openai/gpt-5.2-codex-20260114",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1768409315),
        pricing={'prompt': '0.00000175', 'completion': '0.000014', 'web_search': '0.01', 'input_cache_read': '0.000000175'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 400000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Gpt52CodexModel.model
