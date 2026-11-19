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


class NovaProV1Model(ModelDefinition):
    CANONICAL_ID = "nova-pro-v1"
    MODEL_ID = "amazon/nova-pro-v1"
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
        context_window=300000,
        name="Amazon: Nova Pro 1.0",
        owner="amazon",
        description="Amazon Nova Pro 1.0 is a capable multimodal model from Amazon focused on providing a combination of accuracy, speed, and cost for a wide range of tasks. As of December...",
        canonical_slug="amazon/nova-pro-v1",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1733436303),
        pricing={'prompt': '0.0000008', 'completion': '0.0000032'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Nova', 'instruct_type': None},
        top_provider={'context_length': 300000, 'max_completion_tokens': 5120, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'stop', 'temperature', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = NovaProV1Model.model
