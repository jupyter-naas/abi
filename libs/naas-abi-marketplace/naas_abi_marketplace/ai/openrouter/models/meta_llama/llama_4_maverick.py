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


class Llama4MaverickModel(ModelDefinition):
    CANONICAL_ID = "llama-4-maverick"
    MODEL_ID = "meta-llama/llama-4-maverick"
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
        name="Meta: Llama 4 Maverick",
        owner="meta-llama",
        description="Llama 4 Maverick 17B Instruct (128E) is a high-capacity multimodal language model from Meta, built on a mixture-of-experts (MoE) architecture with 128 experts and 17 billion active parameters per forward...",
        canonical_slug="meta-llama/llama-4-maverick-17b-128e-instruct",
        hugging_face_id="meta-llama/Llama-4-Maverick-17B-128E-Instruct",
        created_at=datetime.fromtimestamp(1743881822),
        pricing={'prompt': '0.00000035', 'completion': '0.000001', 'input_cache_read': '0.00000017'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Llama4', 'instruct_type': None},
        top_provider={'context_length': 524288, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Llama4MaverickModel.model
