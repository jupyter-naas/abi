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


class Qwen3Coder30bA3bInstructModel(ModelDefinition):
    CANONICAL_ID = "qwen3-coder-30b-a3b-instruct"
    MODEL_ID = "qwen/qwen3-coder-30b-a3b-instruct"
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
        name="Qwen: Qwen3 Coder 30B A3B Instruct",
        owner="qwen",
        description="Qwen3-Coder-30B-A3B-Instruct is a 30.5B parameter Mixture-of-Experts (MoE) model with 128 experts (8 active per forward pass), designed for advanced code generation, repository-scale understanding, and agentic tool use. Built on the...",
        canonical_slug="qwen/qwen3-coder-30b-a3b-instruct",
        hugging_face_id="Qwen/Qwen3-Coder-30B-A3B-Instruct",
        created_at=datetime.fromtimestamp(1753972379),
        pricing={'prompt': '0.00000015', 'completion': '0.0000006'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen3', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Qwen3Coder30bA3bInstructModel.model
