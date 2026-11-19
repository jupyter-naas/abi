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


class Qwen3824tA95bModel(ModelDefinition):
    CANONICAL_ID = "qwen3.8-2.4t-a95b"
    MODEL_ID = "qwen/qwen3.8-2.4t-a95b"
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
        context_window=1048576,
        name="Qwen: Qwen3.8 2.4T A95B",
        owner="qwen",
        description="Qwen3.8 2.4T A95B is an open-weight sparse mixture-of-experts model from Qwen and the open-weight variant of [Qwen3.8 Max](/qwen/qwen3.8-max), with 95 billion active parameters out of 2.4 trillion total. It is...",
        canonical_slug="qwen/qwen3.8-2.4t-a95b-20260812",
        hugging_face_id="Qwen/Qwen3.8-2.4T-A95B",
        created_at=datetime.fromtimestamp(1786551702),
        pricing={'prompt': '0.000002', 'completion': '0.000006', 'input_cache_read': '0.00000025'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': 20},
    )


model: ChatModel = Qwen3824tA95bModel.model
