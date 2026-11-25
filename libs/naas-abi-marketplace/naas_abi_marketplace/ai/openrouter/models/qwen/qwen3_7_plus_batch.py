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


class Qwen37PlusBatchModel(ModelDefinition):
    CANONICAL_ID = "qwen3.7-plus:batch"
    MODEL_ID = "qwen/qwen3.7-plus:batch"
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
        context_window=262144,
        name="Qwen: Qwen3.7 Plus (batch)",
        owner="qwen",
        description="Qwen3.7-Plus is a cost-effective model in Alibaba's Qwen3.7 series. It supports text and image input with text output, building on the series' text capabilities with a comprehensive upgrade to its...",
        canonical_slug="qwen/qwen3.7-plus-20260602",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1780491783),
        pricing={'prompt': '0.00000023', 'completion': '0.00000092'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Qwen37PlusBatchModel.model
