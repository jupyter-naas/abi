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


class Mixtral8x22bInstructModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.MIXTRAL_8X22B_INSTRUCT
    MODEL_ID = "mistralai/mixtral-8x22b-instruct"
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
        context_window=65536,
        name="Mistral: Mixtral 8x22B Instruct",
        owner="mistralai",
        description="Mistral's official instruct fine-tuned version of [Mixtral 8x22B](/models/mistralai/mixtral-8x22b). It uses 39B active parameters out of 141B, offering unparalleled cost efficiency for its size. Its strengths include: - strong math, coding,...",
        canonical_slug="mistralai/mixtral-8x22b-instruct",
        hugging_face_id="mistralai/Mixtral-8x22B-Instruct-v0.1",
        created_at=datetime.fromtimestamp(1713312000),
        pricing={'prompt': '0.000002', 'completion': '0.000006', 'input_cache_read': '0.0000002'},
        architecture={'modality': 'text+file->text', 'input_modalities': ['text', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': 'mistral'},
        top_provider={'context_length': 65536, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 0.3},
    )


model: ChatModel = Mixtral8x22bInstructModel.model
