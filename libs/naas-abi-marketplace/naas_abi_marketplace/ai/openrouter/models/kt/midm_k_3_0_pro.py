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


class MidmK30ProModel(ModelDefinition):
    CANONICAL_ID = "midm-k-3.0-pro"
    MODEL_ID = "kt/midm-k-3.0-pro"
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
        context_window=261795,
        name="KT: Mi:dm K 3.0 Pro",
        owner="kt",
        description="Mi:dm K 3.0 Pro is a Mixture-of-Experts reasoning model from KT, with 120B total and 12B active parameters. It uses a hybrid architecture that mixes Mamba, MoE and attention layers.",
        canonical_slug="kt/midm-k-3.0-pro",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1793897701),
        pricing={'prompt': '0.0000002', 'completion': '0.0000008', 'input_cache_read': '0.00000004'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 261795, 'max_completion_tokens': 235615, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MidmK30ProModel.model
