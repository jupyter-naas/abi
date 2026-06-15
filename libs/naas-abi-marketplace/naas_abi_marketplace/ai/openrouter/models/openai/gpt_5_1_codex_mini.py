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


class Gpt51CodexMiniModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_5_1_CODEX_MINI
    MODEL_ID = "openai/gpt-5.1-codex-mini"
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
        name="OpenAI: GPT-5.1-Codex-Mini",
        owner="openai",
        description="GPT-5.1-Codex-Mini is a smaller and faster version of GPT-5.1-Codex",
        canonical_slug="openai/gpt-5.1-codex-mini-20251113",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1763057820),
        pricing={'prompt': '0.00000025', 'completion': '0.000002', 'web_search': '0.01', 'input_cache_read': '0.000000025'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 400000, 'max_completion_tokens': 100000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Gpt51CodexMiniModel.model
