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


class Nova2LiteV1Model(ModelDefinition):
    CANONICAL_ID = "nova-2-lite-v1"
    MODEL_ID = "amazon/nova-2-lite-v1"
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
        name="Amazon: Nova 2 Lite",
        owner="amazon",
        description="Nova 2 Lite is a fast, cost-effective reasoning model for everyday workloads that can process text, images, and videos to generate text. Nova 2 Lite demonstrates standout capabilities in processing...",
        canonical_slug="amazon/nova-2-lite-v1",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1764696672),
        pricing={'prompt': '0.0000003', 'completion': '0.0000025'},
        architecture={'modality': 'text+image+file+video->text', 'input_modalities': ['text', 'image', 'video', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Nova', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 65535, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Nova2LiteV1Model.model
