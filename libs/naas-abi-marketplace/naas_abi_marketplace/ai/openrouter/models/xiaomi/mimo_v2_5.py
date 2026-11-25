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


class MimoV25Model(ModelDefinition):
    CANONICAL_ID = "mimo-v2.5"
    MODEL_ID = "xiaomi/mimo-v2.5"
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
        context_window=1000000,
        name="Xiaomi: MiMo-V2.5",
        owner="xiaomi",
        description="MiMo-V2.5 is a native omnimodal model by Xiaomi. It delivers Pro-level agentic performance at roughly half the inference cost, while surpassing MiMo-V2-Omni in multimodal perception across image and video understanding...",
        canonical_slug="xiaomi/mimo-v2.5-20260422",
        hugging_face_id="XiaomiMiMo/MiMo-V2.5",
        created_at=datetime.fromtimestamp(1776874269),
        pricing={'prompt': '0.0000004', 'completion': '0.000002', 'input_cache_read': '0.00000008'},
        architecture={'modality': 'text+image+audio+video->text', 'input_modalities': ['text', 'audio', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = MimoV25Model.model
