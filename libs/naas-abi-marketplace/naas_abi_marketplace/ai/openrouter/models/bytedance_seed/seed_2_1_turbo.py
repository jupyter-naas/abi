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


class Seed21TurboModel(ModelDefinition):
    CANONICAL_ID = "seed-2-1-turbo"
    MODEL_ID = "bytedance-seed/seed-2-1-turbo"
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
        name="ByteDance Seed: Seed 2.1 Turbo",
        owner="bytedance-seed",
        description="Seed 2.1 Turbo is a multimodal model from ByteDance Seed for coding and long-horizon agent workflows. It is suited for end-to-end software delivery, multi-step task execution, and understanding visual and...",
        canonical_slug="bytedance-seed/seed-2-1-turbo-20260810",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1786552176),
        pricing={'prompt': '0.0000005', 'completion': '0.0000025'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Seed21TurboModel.model
