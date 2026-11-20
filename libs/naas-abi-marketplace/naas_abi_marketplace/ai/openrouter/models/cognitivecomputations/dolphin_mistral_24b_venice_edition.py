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


class DolphinMistral24bVeniceEditionModel(ModelDefinition):
    CANONICAL_ID = "dolphin-mistral-24b-venice-edition"
    MODEL_ID = "cognitivecomputations/dolphin-mistral-24b-venice-edition"
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
        name="Venice: Uncensored",
        owner="cognitivecomputations",
        description="Venice Uncensored Dolphin Mistral 24B Venice Edition is a fine-tuned variant of Mistral-Small-24B-Instruct-2501, developed by dphn.ai in collaboration with Venice.ai. This model is designed as an “uncensored” instruct-tuned LLM, preserving...",
        canonical_slug="venice/uncensored",
        hugging_face_id="cognitivecomputations/Dolphin-Mistral-24B-Venice-Edition",
        created_at=datetime.fromtimestamp(1752094966),
        pricing={'prompt': '0.0000002', 'completion': '0.0000009'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 8192, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'response_format', 'stop', 'temperature', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = DolphinMistral24bVeniceEditionModel.model
