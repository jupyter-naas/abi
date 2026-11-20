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


class CommandAPlusModel(ModelDefinition):
    CANONICAL_ID = "command-a-plus"
    MODEL_ID = "cohere/command-a-plus"
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
        context_window=192000,
        name="Cohere: Command A+",
        owner="cohere",
        description="Command A+ is Cohere's flagship model for enterprise agentic workflows. It accepts text and image inputs with a 192K context window, supports native tool calling with strict tool schemas, structured...",
        canonical_slug="cohere/command-a-plus-05-2026",
        hugging_face_id="CohereLabs/command-a-plus-05-2026-bf16",
        created_at=datetime.fromtimestamp(1790102896),
        pricing={'prompt': '0.0000003', 'completion': '0.0000015', 'input_cache_read': '0.00000015'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Cohere', 'instruct_type': None},
        top_provider={'context_length': 192000, 'max_completion_tokens': 64000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = CommandAPlusModel.model
