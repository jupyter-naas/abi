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


class Nemotron3Nano30bA3bFreeModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.NEMOTRON_3_NANO_30B_A3B_FREE
    MODEL_ID = "nvidia/nemotron-3-nano-30b-a3b:free"
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
        context_window=256000,
        name="Nemotron 3 Nano 30B A3B (free)",
        owner="nvidia",
        description="NVIDIA Nemotron 3 Nano 30B A3B is a small language MoE model with highest compute efficiency and accuracy for developers to build specialized agentic AI systems. The model is fully...",
        canonical_slug="nvidia/nemotron-3-nano-30b-a3b",
        hugging_face_id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
        created_at=datetime.fromtimestamp(1765731275),
        pricing={'prompt': '0', 'completion': '0'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 256000, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'seed', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Nemotron3Nano30bA3bFreeModel.model
