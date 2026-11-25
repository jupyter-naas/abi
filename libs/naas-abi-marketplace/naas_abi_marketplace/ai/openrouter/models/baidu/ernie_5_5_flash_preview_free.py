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


class Ernie55FlashPreviewFreeModel(ModelDefinition):
    CANONICAL_ID = "ernie-5.5-flash-preview:free"
    MODEL_ID = "baidu/ernie-5.5-flash-preview:free"
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
        name="Baidu: ERNIE-5.5-Flash-Preview (free)",
        owner="baidu",
        description="ERNIE 5.5 Flash Preview is the latest foundation model in the ERNIE family, with comprehensive improvements in coding, agentic capabilities, knowledge work, and deep research. It has 280 billion total...",
        canonical_slug="baidu/ernie-5.5-flash-preview-20261110",
        hugging_face_id="baidu/ERNIE-5.5-Flash-Preview",
        created_at=datetime.fromtimestamp(1794333533),
        pricing={'prompt': '0', 'completion': '0'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1024000, 'max_completion_tokens': 921600, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Ernie55FlashPreviewFreeModel.model
