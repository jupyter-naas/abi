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


class UiTars157bModel(ModelDefinition):
    CANONICAL_ID = "ui-tars-1.5-7b"
    MODEL_ID = "bytedance/ui-tars-1.5-7b"
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
        context_window=128000,
        name="ByteDance: UI-TARS 7B ",
        owner="bytedance",
        description="UI-TARS-1.5 is a multimodal vision-language agent optimized for GUI-based environments, including desktop interfaces, web browsers, mobile systems, and games. Built by ByteDance, it builds upon the UI-TARS framework with reinforcement...",
        canonical_slug="bytedance/ui-tars-1.5-7b",
        hugging_face_id="ByteDance-Seed/UI-TARS-1.5-7B",
        created_at=datetime.fromtimestamp(1753205056),
        pricing={'prompt': '0.0000001', 'completion': '0.0000002', 'input_cache_read': '0.0000001'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 2048, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = UiTars157bModel.model
