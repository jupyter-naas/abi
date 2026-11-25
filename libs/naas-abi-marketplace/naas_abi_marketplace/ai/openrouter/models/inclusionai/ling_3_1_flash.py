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


class Ling31FlashModel(ModelDefinition):
    CANONICAL_ID = "ling-3.1-flash"
    MODEL_ID = "inclusionai/ling-3.1-flash"
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
        name="inclusionAI: Ling 3.1 Flash",
        owner="inclusionai",
        description="Ling 3.1 Flash is a hybrid reasoning mixture-of-experts model from inclusionAI, with 25B active parameters out of 560B total.",
        canonical_slug="inclusionai/ling-3.1-flash-20261002",
        hugging_face_id="inclusionAI/Ling-3.1-flash",
        created_at=datetime.fromtimestamp(1790950024),
        pricing={'prompt': '0.000000045', 'completion': '0.000000135', 'input_cache_read': '0.000000009'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 262144, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'repetition_penalty', 'seed', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Ling31FlashModel.model
