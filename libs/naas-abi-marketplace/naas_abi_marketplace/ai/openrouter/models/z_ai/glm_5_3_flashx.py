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


class Glm53FlashxModel(ModelDefinition):
    CANONICAL_ID = "glm-5.3-flashx"
    MODEL_ID = "z-ai/glm-5.3-flashx"
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
        name="Z.ai: GLM 5.3 FlashX",
        owner="z-ai",
        description="GLM-5.3-FlashX is the high-speed variant of Z.ai's GLM-5.3-Flash, a native multimodal model delivering inference speeds of up to 200 tokens/s. Built on the same hybrid sparse and linear attention architecture...",
        canonical_slug="z-ai/glm-5.3-flashx-20260918",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1789744020),
        pricing={'prompt': '0.00000037', 'completion': '0.00000125', 'input_cache_read': '0.000000075'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95},
    )


model: ChatModel = Glm53FlashxModel.model
