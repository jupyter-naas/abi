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


class Ripple65bPreviewModel(ModelDefinition):
    CANONICAL_ID = "ripple-65b-preview"
    MODEL_ID = "ricursiveai/ripple-65b-preview"
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
        name="Ricursive: Ripple 65B Preview",
        owner="ricursiveai",
        description="Ripple-65B-Preview by ricursiveAI, a 65B model with native tool calling, served in BF16.",
        canonical_slug="ricursiveai/ripple-65b-preview-20261104",
        hugging_face_id="ricursiveAI/Ripple-65B-Preview",
        created_at=datetime.fromtimestamp(1793818990),
        pricing={'prompt': '0.0000001', 'completion': '0.0000003', 'input_cache_read': '0.000000025'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Ripple65bPreviewModel.model
