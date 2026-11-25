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


class SolarMini4Model(ModelDefinition):
    CANONICAL_ID = "solar-mini4"
    MODEL_ID = "upstage/solar-mini4"
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
        context_window=524288,
        name="Upstage: Solar Mini 4",
        owner="upstage",
        description="Solar Mini 4 is Upstage's compact, cost-efficient language model, a 35B-parameter mixture-of-experts with 3B active parameters and a 524K context window. It is built for agentic use cases where response...",
        canonical_slug="upstage/solar-mini4-20260922",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1790160358),
        pricing={'prompt': '0.00000005', 'completion': '0.0000002', 'input_cache_read': '0.000000005'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 524288, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'parallel_tool_calls', 'presence_penalty', 'reasoning', 'reasoning_effort', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = SolarMini4Model.model
