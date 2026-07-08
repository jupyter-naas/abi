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


class Nemotron3Ultra550bA55bFreeModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.NEMOTRON_3_ULTRA_550B_A55B_FREE
    MODEL_ID = "nvidia/nemotron-3-ultra-550b-a55b:free"
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
        name="Nemotron 3 Ultra (free)",
        owner="nvidia",
        description="NVIDIA Nemotron 3 Ultra is an open frontier-reasoning and orchestration model from NVIDIA, with 55B active parameters out of 550B total (MoE). Built on a hybrid Transformer-Mamba mixture-of-experts architecture, it...",
        canonical_slug="nvidia/nemotron-3-ultra-550b-a55b-20260604",
        hugging_face_id="nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16",
        created_at=datetime.fromtimestamp(1780551208),
        pricing={'prompt': '0', 'completion': '0'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'seed', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Nemotron3Ultra550bA55bFreeModel.model
