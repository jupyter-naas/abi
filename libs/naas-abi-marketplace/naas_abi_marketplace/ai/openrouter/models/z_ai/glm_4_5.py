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


class Glm45Model(ModelDefinition):
    CANONICAL_ID = "glm-4.5"
    MODEL_ID = "z-ai/glm-4.5"
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
        name="Z.ai: GLM 4.5",
        owner="z-ai",
        description="GLM-4.5 is our latest flagship foundation model, purpose-built for agent-based applications. It leverages a Mixture-of-Experts (MoE) architecture and supports a context length of up to 128k tokens. GLM-4.5 delivers significantly...",
        canonical_slug="z-ai/glm-4.5",
        hugging_face_id="zai-org/GLM-4.5",
        created_at=datetime.fromtimestamp(1753471347),
        pricing={'prompt': '0.0000006', 'completion': '0.0000022', 'input_cache_read': '0.00000011'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 98304, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': 0.75, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Glm45Model.model
