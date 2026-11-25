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


class Ling30FlashVlModel(ModelDefinition):
    CANONICAL_ID = "ling-3.0-flash-vl"
    MODEL_ID = "inclusionai/ling-3.0-flash-vl"
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
        context_window=131072,
        name="inclusionAI: Ling 3.0 Flash VL",
        owner="inclusionai",
        description="Ling 3.0 Flash VL builds on Ling 3.0 Flash (124B total / 5.5B active MoE from InclusionAI), further strengthening its language capabilities while adding native visual perception and advanced visual...",
        canonical_slug="inclusionai/ling-3.0-flash-vl-20260910",
        hugging_face_id="inclusionAI/Ling-3.0-flash-VL",
        created_at=datetime.fromtimestamp(1789056114),
        pricing={'prompt': '0.00000006', 'completion': '0.00000018', 'input_cache_read': '0.000000012'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Ling30FlashVlModel.model
