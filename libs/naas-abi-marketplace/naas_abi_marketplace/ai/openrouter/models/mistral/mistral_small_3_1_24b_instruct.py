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


class MistralSmall3124bInstructModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.MISTRAL_SMALL_3_1_24B_INSTRUCT
    MODEL_ID = "mistralai/mistral-small-3.1-24b-instruct"
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
        name="Mistral: Mistral Small 3.1 24B",
        owner="mistralai",
        description="Mistral Small 3.1 24B Instruct is an upgraded variant of Mistral Small 3 (2501), featuring 24 billion parameters with advanced multimodal capabilities. It provides state-of-the-art performance in text-based reasoning and...",
        canonical_slug="mistralai/mistral-small-3.1-24b-instruct-2503",
        hugging_face_id="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        created_at=datetime.fromtimestamp(1742238937),
        pricing={'prompt': '0.000000351', 'completion': '0.000000555'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 128000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'seed', 'stop', 'temperature', 'top_k', 'top_p'],
        default_parameters={'temperature': 0.3},
    )


model: ChatModel = MistralSmall3124bInstructModel.model
