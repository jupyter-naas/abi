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


class Lfm317bModel(ModelDefinition):
    CANONICAL_ID = "lfm-3-1.7b"
    MODEL_ID = "liquid/lfm-3-1.7b"
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
        name="LiquidAI: LFM3-1.7B",
        owner="liquid",
        description="A compact 1.7B-parameter text model with a 256K-token context, post-trained for agents, tool calling, and structured outputs. It reasons before it answers. Prompts and outputs may be retained and used...",
        canonical_slug="liquid/lfm-3-1.7b-20261106",
        hugging_face_id="LiquidAI/LFM3-1.7B",
        created_at=datetime.fromtimestamp(1794009477),
        pricing={'prompt': '0.00000008', 'completion': '0.0000002', 'input_cache_read': '0.00000002'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 8192, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_completion_tokens', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 0.1, 'top_k': 50, 'repetition_penalty': 1.1},
    )


model: ChatModel = Lfm317bModel.model
