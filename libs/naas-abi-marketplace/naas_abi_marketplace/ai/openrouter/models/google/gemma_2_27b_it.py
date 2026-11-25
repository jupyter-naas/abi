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


class Gemma227bItModel(ModelDefinition):
    CANONICAL_ID = "gemma-2-27b-it"
    MODEL_ID = "google/gemma-2-27b-it"
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
        context_window=8192,
        name="Google: Gemma 2 27B",
        owner="google",
        description="Gemma 2 27B by Google is an open model built from the same research and technology used to create the [Gemini models](/models?q=gemini). Gemma models are well-suited for a variety of...",
        canonical_slug="google/gemma-2-27b-it",
        hugging_face_id="google/gemma-2-27b-it",
        created_at=datetime.fromtimestamp(1720828800),
        pricing={'prompt': '0.00000065', 'completion': '0.00000065'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': 'gemma'},
        top_provider={'context_length': 8192, 'max_completion_tokens': 2048, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gemma227bItModel.model
