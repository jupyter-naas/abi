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


class SwitchyardModel(ModelDefinition):
    CANONICAL_ID = "switchyard"
    MODEL_ID = "nvidia/switchyard"
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
        name="NVIDIA: Switchyard",
        owner="nvidia",
        description="Switchyard is an open-source model routing system that switches between multiple models to optimize the cost of requests. By default it will use OpenRouter market data to select the most...",
        canonical_slug="nvidia/switchyard",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1790025947),
        pricing={'prompt': '-1', 'completion': '-1'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Router', 'instruct_type': None},
        top_provider={'context_length': None, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=[],
        default_parameters={},
    )


model: ChatModel = SwitchyardModel.model
