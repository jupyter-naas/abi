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


class Seed20MiniModel(ModelDefinition):
    CANONICAL_ID = "seed-2.0-mini"
    MODEL_ID = "bytedance-seed/seed-2.0-mini"
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
        name="ByteDance Seed: Seed-2.0-Mini",
        owner="bytedance-seed",
        description="Seed-2.0-mini targets latency-sensitive, high-concurrency, and cost-sensitive scenarios, emphasizing fast response and flexible inference deployment. It delivers performance comparable to ByteDance-Seed-1.6, supports 256k context, four reasoning effort modes (minimal/low/medium/high), multimodal understanding,...",
        canonical_slug="bytedance-seed/seed-2.0-mini-20260224",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1772131107),
        pricing={'prompt': '0.0000001', 'completion': '0.0000004', 'overrides': [{'min_prompt_tokens': 128000, 'prompt': '0.0000002', 'completion': '0.0000008'}]},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Seed20MiniModel.model
