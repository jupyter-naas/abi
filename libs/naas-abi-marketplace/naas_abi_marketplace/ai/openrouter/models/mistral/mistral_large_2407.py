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


class MistralLarge2407Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.MISTRAL_LARGE_2407
    MODEL_ID = "mistralai/mistral-large-2407"
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
        name="Mistral Large 2407",
        owner="mistralai",
        description="This is Mistral AI's flagship model, Mistral Large 2 (version mistral-large-2407). It's a proprietary weights-available model and excels at reasoning, code, JSON, chat, and more. Read the launch announcement [here](https://mistral.ai/news/mistral-large-2407/)....",
        canonical_slug="mistralai/mistral-large-2407",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1731978415),
        pricing={'prompt': '0.000002', 'completion': '0.000006', 'input_cache_read': '0.0000002'},
        architecture={'modality': 'text+file->text', 'input_modalities': ['text', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 0.3},
    )


model: ChatModel = MistralLarge2407Model.model
