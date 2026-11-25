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


class Aion30Model(ModelDefinition):
    CANONICAL_ID = "aion-3.0"
    MODEL_ID = "aion-labs/aion-3.0"
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
        context_window=131072,
        name="AionLabs: Aion-3.0",
        owner="aion-labs",
        description="Aion-3.0 is a multi-model roleplaying and storytelling system from AionLabs, built on the GLM family of models. It uses a collaborative generation process in which multiple specialized models each contribute...",
        canonical_slug="aion-labs/aion-3.0-20260707",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1783443095),
        pricing={'prompt': '0.000003', 'completion': '0.000006', 'input_cache_read': '0.00000075'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Aion30Model.model
