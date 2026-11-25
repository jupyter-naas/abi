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


class Qwen330bA3bInstruct2507Model(ModelDefinition):
    CANONICAL_ID = "qwen3-30b-a3b-instruct-2507"
    MODEL_ID = "qwen/qwen3-30b-a3b-instruct-2507"
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
        name="Qwen: Qwen3 30B A3B Instruct 2507",
        owner="qwen",
        description="Qwen3-30B-A3B-Instruct-2507 is a 30.5B-parameter mixture-of-experts language model from Qwen, with 3.3B active parameters per inference. It operates in non-thinking mode and is designed for high-quality instruction following, multilingual understanding, and...",
        canonical_slug="qwen/qwen3-30b-a3b-instruct-2507",
        hugging_face_id="Qwen/Qwen3-30B-A3B-Instruct-2507",
        created_at=datetime.fromtimestamp(1753806965),
        pricing={'prompt': '0.0000001', 'completion': '0.0000003', 'input_cache_read': '0.0000001'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen3', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Qwen330bA3bInstruct2507Model.model
