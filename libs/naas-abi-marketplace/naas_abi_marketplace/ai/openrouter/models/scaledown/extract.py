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


class ExtractModel(ModelDefinition):
    CANONICAL_ID = "extract"
    MODEL_ID = "scaledown/extract"
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
        name="ScaleDown: Extract",
        owner="scaledown",
        description="Extract is a description-driven entity extraction model from ScaleDown. Instead of a fixed set of entity types, callers describe the fields they want in plain English through `provider.options.scaledown.entities`, and the...",
        canonical_slug="scaledown/extract-20260928",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1791893351),
        pricing={'prompt': '0.00000004', 'completion': '0'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 900000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['max_tokens'],
        default_parameters={},
    )


model: ChatModel = ExtractModel.model
