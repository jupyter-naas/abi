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


class Hy4FlashModel(ModelDefinition):
    CANONICAL_ID = "hy4-flash"
    MODEL_ID = "tencent/hy4-flash"
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
        name="Tencent: Hy4 flash",
        owner="tencent",
        description="Hy4 flash is a cost-efficient variant of [Hy4](https://openrouter.ai/tencent/hy4) from Tencent, served with roughly a quarter of the flagship's parameter count for lower latency and cost. It targets code assistance, agent...",
        canonical_slug="tencent/hy4-flash-20261116",
        hugging_face_id="tencent/Hy4-flash",
        created_at=datetime.fromtimestamp(1794838706),
        pricing={'prompt': '0.000000035', 'completion': '0.0000001405', 'input_cache_read': '0.0000000015'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools'],
        default_parameters={},
    )


model: ChatModel = Hy4FlashModel.model
