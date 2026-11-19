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


class NovaPremierV1Model(ModelDefinition):
    CANONICAL_ID = "nova-premier-v1"
    MODEL_ID = "amazon/nova-premier-v1"
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
        name="Amazon: Nova Premier 1.0",
        owner="amazon",
        description="Amazon Nova Premier is the most capable of Amazon’s multimodal models for complex reasoning tasks and for use as the best teacher for distilling custom models.",
        canonical_slug="amazon/nova-premier-v1",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1761950332),
        pricing={'prompt': '0.0000025', 'completion': '0.0000125', 'input_cache_read': '0.000000625'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Nova', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 32000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'stop', 'temperature', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = NovaPremierV1Model.model
