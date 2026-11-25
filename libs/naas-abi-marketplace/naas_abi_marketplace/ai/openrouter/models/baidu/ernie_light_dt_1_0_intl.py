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


class ErnieLightDt10IntlModel(ModelDefinition):
    CANONICAL_ID = "ernie-light-dt-1.0-intl"
    MODEL_ID = "baidu/ernie-light-dt-1.0-intl"
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
        context_window=1024000,
        name="Baidu: ERNIE-Light-DT-1.0",
        owner="baidu",
        description="ERNIE-Light-DT-1.0 is based on open-source GLM models and includes research findings from Baidu Search's Lightning large model. It features Baidu Sparse Attention (BSA), a unique sparse attention mechanism developed by...",
        canonical_slug="baidu/ernie-light-dt-1.0-intl-20261110",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1794331260),
        pricing={'prompt': '0.00000113', 'completion': '0.00000394', 'input_cache_read': '0.000000113'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1024000, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = ErnieLightDt10IntlModel.model
