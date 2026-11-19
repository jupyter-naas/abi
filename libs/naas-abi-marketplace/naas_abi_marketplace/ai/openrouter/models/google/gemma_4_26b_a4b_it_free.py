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


class Gemma426bA4bItFreeModel(ModelDefinition):
    CANONICAL_ID = "gemma-4-26b-a4b-it:free"
    MODEL_ID = "google/gemma-4-26b-a4b-it:free"
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
        name="Google: Gemma 4 26B A4B  (free)",
        owner="google",
        description="Gemma 4 26B A4B IT is an instruction-tuned Mixture-of-Experts (MoE) model from Google DeepMind. Despite 25.2B total parameters, only 3.8B activate per token during inference — delivering near-31B quality at...",
        canonical_slug="google/gemma-4-26b-a4b-it-20260403",
        hugging_face_id="google/gemma-4-26B-A4B-it",
        created_at=datetime.fromtimestamp(1775227989),
        pricing={'prompt': '0', 'completion': '0'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['image', 'text', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Gemma', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'seed', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': 64},
    )


model: ChatModel = Gemma426bA4bItFreeModel.model
