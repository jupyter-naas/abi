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


class Glm46vModel(ModelDefinition):
    CANONICAL_ID = "glm-4.6v"
    MODEL_ID = "z-ai/glm-4.6v"
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
        name="Z.ai: GLM 4.6V",
        owner="z-ai",
        description="GLM-4.6V is a large multimodal model designed for high-fidelity visual understanding and long-context reasoning across images, documents, and mixed media. It supports up to 128K tokens, processes complex page layouts...",
        canonical_slug="z-ai/glm-4.6-20251208",
        hugging_face_id="zai-org/GLM-4.6V",
        created_at=datetime.fromtimestamp(1765207462),
        pricing={'prompt': '0.0000003', 'completion': '0.0000009', 'input_cache_read': '0.00000005'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['image', 'text', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': 0.8, 'top_p': 0.6, 'frequency_penalty': None},
    )


model: ChatModel = Glm46vModel.model
