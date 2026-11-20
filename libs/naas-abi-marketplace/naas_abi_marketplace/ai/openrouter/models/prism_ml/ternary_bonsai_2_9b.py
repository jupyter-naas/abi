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


class TernaryBonsai29bModel(ModelDefinition):
    CANONICAL_ID = "ternary-bonsai-2-9b"
    MODEL_ID = "prism-ml/ternary-bonsai-2-9b"
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
        name="PrismML: Ternary Bonsai 2 9B",
        owner="prism-ml",
        description="Ternary Bonsai 2 9B is PrismML’s compact, open-weight language model for conversational AI, reasoning, and tool use. Built on Qwen3.5, it uses ternary weights packed into 2 bits for efficient...",
        canonical_slug="prism-ml/ternary-bonsai-2-9b-20261015",
        hugging_face_id="prism-ml/Ternary-Bonsai-2-9B-gguf",
        created_at=datetime.fromtimestamp(1792130995),
        pricing={'prompt': '0.00000008', 'completion': '0.00000013', 'input_cache_read': '0.00000004'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': 20},
    )


model: ChatModel = TernaryBonsai29bModel.model
