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


class Gpt4oBatchModel(ModelDefinition):
    CANONICAL_ID = "gpt-4o:batch"
    MODEL_ID = "openai/gpt-4o:batch"
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
        context_window=128000,
        name="OpenAI: GPT-4o (batch)",
        owner="openai",
        description="GPT-4o (\"o\" for \"omni\") is OpenAI's latest AI model, supporting both text and image inputs with text outputs. It maintains the intelligence level of [GPT-4 Turbo](/models/openai/gpt-4-turbo) while being twice as...",
        canonical_slug="openai/gpt-4o",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1715558400),
        pricing={'prompt': '0.00000125', 'completion': '0.000005', 'web_search': '0.01', 'input_cache_read': '0.000000625'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 16384, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'prediction', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p', 'web_search_options'],
        default_parameters={},
    )


model: ChatModel = Gpt4oBatchModel.model
