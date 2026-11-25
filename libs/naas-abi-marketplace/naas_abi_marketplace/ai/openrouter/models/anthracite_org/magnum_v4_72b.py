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


class MagnumV472bModel(ModelDefinition):
    CANONICAL_ID = "magnum-v4-72b"
    MODEL_ID = "anthracite-org/magnum-v4-72b"
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
        context_window=32768,
        name="Magnum v4 72B",
        owner="anthracite-org",
        description="This is a series of models designed to replicate the prose quality of the Claude 3 models, specifically Sonnet(https://openrouter.ai/anthropic/claude-3.5-sonnet) and Opus(https://openrouter.ai/anthropic/claude-3-opus).\n\nThe model is fine-tuned on top of [Qwen2.5 72B](https://openrouter.ai/qwen/qwen-2.5-72b-instruct).",
        canonical_slug="anthracite-org/magnum-v4-72b",
        hugging_face_id="anthracite-org/magnum-v4-72b",
        created_at=datetime.fromtimestamp(1729555200),
        pricing={'prompt': '0.0000025', 'completion': '0.000005', 'input_cache_read': '0.0000025'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': 'chatml'},
        top_provider={'context_length': 32768, 'max_completion_tokens': 4096, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_a', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MagnumV472bModel.model
