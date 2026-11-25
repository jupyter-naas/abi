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


class Qwen35122bA10bModel(ModelDefinition):
    CANONICAL_ID = "qwen3.5-122b-a10b"
    MODEL_ID = "qwen/qwen3.5-122b-a10b"
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
        name="Qwen: Qwen3.5-122B-A10B",
        owner="qwen",
        description="The Qwen3.5 122B-A10B native vision-language model is built on a hybrid architecture that integrates a linear attention mechanism with a sparse mixture-of-experts model, achieving higher inference efficiency. In terms of...",
        canonical_slug="qwen/qwen3.5-122b-a10b-20260224",
        hugging_face_id="Qwen/Qwen3.5-122B-A10B",
        created_at=datetime.fromtimestamp(1772053789),
        pricing={'prompt': '0.00000026', 'completion': '0.00000208'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Qwen3', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 0.6, 'top_p': 0.95, 'top_k': 20, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Qwen35122bA10bModel.model
