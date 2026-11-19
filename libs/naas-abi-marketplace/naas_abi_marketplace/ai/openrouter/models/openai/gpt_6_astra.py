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


class Gpt6AstraModel(ModelDefinition):
    CANONICAL_ID = "gpt-6-astra"
    MODEL_ID = "openai/gpt-6-astra"
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
        context_window=1050000,
        name="OpenAI: GPT-6 Astra",
        owner="openai",
        description="GPT-6 Astra is OpenAI's flagship model for demanding end-to-end work. It is suited for advanced analysis, software engineering, deep research, scientific work, and document creation, with particular strengths in long-horizon...",
        canonical_slug="openai/gpt-6-astra-20260903",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1788552838),
        pricing={'prompt': '0.00001', 'completion': '0.00005', 'web_search': '0.01', 'input_cache_read': '0.000001', 'input_cache_write': '0.0000125', 'overrides': [{'min_prompt_tokens': 272000, 'prompt': '0.00002', 'completion': '0.000075', 'input_cache_read': '0.000002', 'input_cache_write': '0.000025'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['file', 'image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 1050000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools', 'verbosity'],
        default_parameters={},
    )


model: ChatModel = Gpt6AstraModel.model
