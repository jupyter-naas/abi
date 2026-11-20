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


class NovaMicroV1Model(ModelDefinition):
    CANONICAL_ID = "nova-micro-v1"
    MODEL_ID = "amazon/nova-micro-v1"
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
        context_window=128000,
        name="Amazon: Nova Micro 1.0",
        owner="amazon",
        description="Amazon Nova Micro 1.0 is a text-only model that delivers the lowest latency responses in the Amazon Nova family of models at a very low cost. With a context length...",
        canonical_slug="amazon/nova-micro-v1",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1733437237),
        pricing={'prompt': '0.000000035', 'completion': '0.00000014'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Nova', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 5120, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'stop', 'temperature', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = NovaMicroV1Model.model
