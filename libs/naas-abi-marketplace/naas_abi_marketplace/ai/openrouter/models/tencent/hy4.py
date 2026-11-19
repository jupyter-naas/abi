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


class Hy4Model(ModelDefinition):
    CANONICAL_ID = "hy4"
    MODEL_ID = "tencent/hy4"
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
        name="Tencent: Hy4",
        owner="tencent",
        description="The official release of Hy4 delivers comprehensive and substantial improvements over Hy4 Preview, with particularly strong gains in agentic capabilities and performance across a wide range of long-horizon, real-world productivity...",
        canonical_slug="tencent/hy4-20261104",
        hugging_face_id="tencent/Hy4",
        created_at=datetime.fromtimestamp(1793766031),
        pricing={'prompt': '0.000000417', 'completion': '0.0000012505', 'input_cache_read': '0.000000021'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools'],
        default_parameters={},
    )


model: ChatModel = Hy4Model.model
