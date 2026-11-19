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


class QwenPlusModel(ModelDefinition):
    CANONICAL_ID = "qwen-plus"
    MODEL_ID = "qwen/qwen-plus"
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
        context_window=1000000,
        name="Qwen: Qwen-Plus",
        owner="qwen",
        description="Qwen-Plus, based on the Qwen2.5 foundation model, is a 131K context model with a balanced performance, speed, and cost combination.",
        canonical_slug="qwen/qwen-plus-2025-01-25",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1738409840),
        pricing={'prompt': '0.00000026', 'completion': '0.00000078', 'input_cache_read': '0.000000052', 'input_cache_write': '0.000000325', 'overrides': [{'min_prompt_tokens': 256000, 'prompt': '0.00000078', 'completion': '0.00000234', 'input_cache_read': '0.000000156', 'input_cache_write': '0.000000975'}]},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logprobs', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = QwenPlusModel.model
