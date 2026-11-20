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


class MimoV26ProUltraspeedModel(ModelDefinition):
    CANONICAL_ID = "mimo-v2.6-pro-ultraspeed"
    MODEL_ID = "xiaomi/mimo-v2.6-pro-ultraspeed"
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
        context_window=1048576,
        name="Xiaomi: MiMo-V2.6-Pro-UltraSpeed",
        owner="xiaomi",
        description="MiMo-V2.6-Pro-UltraSpeed is the fast speed edition of Xiaomi's flagship foundation model, MiMo-V2.6-Pro. Built from the same 1T MiMo-V2.6-Pro checkpoint, it matches the original model in quality while delivering roughly 10x...",
        canonical_slug="xiaomi/mimo-v2.6-pro-ultraspeed-20260921",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1790021267),
        pricing={'prompt': '0.00000435', 'completion': '0.0000087', 'input_cache_read': '0.000000036'},
        architecture={'modality': 'text+image+audio+video->text', 'input_modalities': ['text', 'image', 'video', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'frequency_penalty': 0},
    )


model: ChatModel = MimoV26ProUltraspeedModel.model
