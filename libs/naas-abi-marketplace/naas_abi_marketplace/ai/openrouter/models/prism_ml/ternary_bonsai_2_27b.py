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


class TernaryBonsai227bModel(ModelDefinition):
    CANONICAL_ID = "ternary-bonsai-2-27b"
    MODEL_ID = "prism-ml/ternary-bonsai-2-27b"
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
        name="PrismML: Ternary Bonsai 2 27B",
        owner="prism-ml",
        description="Bonsai 2 27B is a 27B-parameter reasoning model from PrismML derived from Qwen3.8-27B. It supports coding, mathematics, tool calling, and image understanding with a 262K-token context window. Ternary compression shrinks...",
        canonical_slug="prism-ml/ternary-bonsai-2-27b-20260918",
        hugging_face_id="prism-ml/Ternary-Bonsai-2-27B-gguf",
        created_at=datetime.fromtimestamp(1789754046),
        pricing={'prompt': '0.000000075', 'completion': '0.0000005', 'input_cache_read': '0.0000000375'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': 20},
    )


model: ChatModel = TernaryBonsai227bModel.model
