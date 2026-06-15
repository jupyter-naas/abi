from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class MistralSmall2603Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.MISTRAL_SMALL_2603
    MODEL_ID = "mistralai/mistral-small-2603"
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
        context_window=262144,
        name="Mistral: Mistral Small 4",
        owner="mistralai",
        description="Mistral Small 4 is the next major release in the Mistral Small family, unifying the capabilities of several flagship Mistral models into a single system. It combines strong reasoning from...",
        canonical_slug="mistralai/mistral-small-2603",
        hugging_face_id="mistralai/Mistral-Small-4-119B-2603",
        created_at=datetime.fromtimestamp(1773695685),
        pricing={'prompt': '0.00000015', 'completion': '0.0000006', 'input_cache_read': '0.000000015'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = MistralSmall2603Model.model
