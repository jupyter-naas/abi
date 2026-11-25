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


class Qwen35Flash0223Model(ModelDefinition):
    CANONICAL_ID = "qwen3.5-flash-02-23"
    MODEL_ID = "qwen/qwen3.5-flash-02-23"
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
        name="Qwen: Qwen3.5-Flash",
        owner="qwen",
        description="The Qwen3.5 native vision-language Flash models are built on a hybrid architecture that integrates a linear attention mechanism with a sparse mixture-of-experts model, achieving higher inference efficiency. Compared to the...",
        canonical_slug="qwen/qwen3.5-flash-20260224",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1772053776),
        pricing={'prompt': '0.000000065', 'completion': '0.00000026'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Qwen3', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Qwen35Flash0223Model.model
