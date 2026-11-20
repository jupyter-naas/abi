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


class SakanaNamazuModel(ModelDefinition):
    CANONICAL_ID = "sakana-namazu"
    MODEL_ID = "sakana/sakana-namazu"
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
        name="Sakana: Sakana Namazu",
        owner="sakana",
        description="Sakana Namazu is a Japanese-specialized reasoning model from Sakana AI, based on Kimi K2.6 with additional training for Japanese language and business contexts. It is suited for Japanese instruction following,...",
        canonical_slug="sakana/namazu-20260811",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1786410129),
        pricing={'prompt': '0.00000095', 'completion': '0.000004', 'web_search': '0.007', 'input_cache_read': '0.00000015'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'reasoning', 'reasoning_effort', 'structured_outputs', 'tool_choice', 'tools', 'web_search_options'],
        default_parameters={},
    )


model: ChatModel = SakanaNamazuModel.model
