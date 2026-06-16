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


class Nemotron3NanoOmni30bA3bReasoningFreeModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.NEMOTRON_3_NANO_OMNI_30B_A3B_REASONING_FREE
    MODEL_ID = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
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
        name="NVIDIA: Nemotron 3 Nano Omni (free)",
        owner="nvidia",
        description="NVIDIA Nemotron™ 3 Nano Omni is a 30B-A3B open multimodal model designed to function as a perception and context sub-agent in enterprise agent systems. It accepts text, image, video, and...",
        canonical_slug="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning-20260428",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1777393095),
        pricing={'prompt': '0', 'completion': '0'},
        architecture={'modality': 'text+image+audio+video->text', 'input_modalities': ['text', 'audio', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 256000, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'seed', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 0.6, 'top_p': 0.95, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Nemotron3NanoOmni30bA3bReasoningFreeModel.model
