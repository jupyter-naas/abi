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


class Devstral2512Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.DEVSTRAL_2512
    MODEL_ID = "mistralai/devstral-2512"
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
        name="Devstral 2 2512",
        owner="mistralai",
        description="Devstral 2 is a state-of-the-art open-source model by Mistral AI specializing in agentic coding. It is a 123B-parameter dense transformer model supporting a 256K context window. Devstral 2 supports exploring...",
        canonical_slug="mistralai/devstral-2512",
        hugging_face_id="mistralai/Devstral-2-123B-Instruct-2512",
        created_at=datetime.fromtimestamp(1765285419),
        pricing={'prompt': '0.0000004', 'completion': '0.000002', 'input_cache_read': '0.00000004'},
        architecture={'modality': 'text+file->text', 'input_modalities': ['text', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 0.3, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Devstral2512Model.model
