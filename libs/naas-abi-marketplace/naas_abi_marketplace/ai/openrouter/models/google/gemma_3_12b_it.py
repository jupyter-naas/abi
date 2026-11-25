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


class Gemma312bItModel(ModelDefinition):
    CANONICAL_ID = "gemma-3-12b-it"
    MODEL_ID = "google/gemma-3-12b-it"
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
        context_window=131072,
        name="Google: Gemma 3 12B",
        owner="google",
        description="Gemma 3 introduces multimodality, supporting vision-language input and text outputs. It handles context windows up to 128k tokens, understands over 140 languages, and offers improved math, reasoning, and chat capabilities,...",
        canonical_slug="google/gemma-3-12b-it",
        hugging_face_id="google/gemma-3-12b-it",
        created_at=datetime.fromtimestamp(1741902625),
        pricing={'prompt': '0.00000005', 'completion': '0.00000015'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': 'gemma'},
        top_provider={'context_length': 131072, 'max_completion_tokens': 16384, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gemma312bItModel.model
