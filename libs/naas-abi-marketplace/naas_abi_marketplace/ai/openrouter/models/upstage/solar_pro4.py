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


class SolarPro4Model(ModelDefinition):
    CANONICAL_ID = "solar-pro4"
    MODEL_ID = "upstage/solar-pro4"
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
        name="Upstage: Solar Pro 4",
        owner="upstage",
        description="Solar Pro 4 is Upstage's cost-efficient large language model, featuring a 524K context window. It is built for long-horizon tasks and agentic workflows, with strong capabilities in office productivity, document-intensive...",
        canonical_slug="upstage/solar-pro4-20260810",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1786371636),
        pricing={'prompt': '0.00000015', 'completion': '0.0000006', 'input_cache_read': '0.00000003'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 524288, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'parallel_tool_calls', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = SolarPro4Model.model
