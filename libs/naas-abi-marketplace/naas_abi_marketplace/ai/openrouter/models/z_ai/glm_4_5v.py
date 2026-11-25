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


class Glm45vModel(ModelDefinition):
    CANONICAL_ID = "glm-4.5v"
    MODEL_ID = "z-ai/glm-4.5v"
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
        context_window=65536,
        name="Z.ai: GLM 4.5V",
        owner="z-ai",
        description="GLM-4.5V is a vision-language foundation model for multimodal agent applications. Built on a Mixture-of-Experts (MoE) architecture with 106B parameters and 12B activated parameters, it achieves state-of-the-art results in video understanding,...",
        canonical_slug="z-ai/glm-4.5v",
        hugging_face_id="zai-org/GLM-4.5V",
        created_at=datetime.fromtimestamp(1754922288),
        pricing={'prompt': '0.0000006', 'completion': '0.0000018', 'input_cache_read': '0.00000011'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 65536, 'max_completion_tokens': 16384, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': 0.75, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Glm45vModel.model
