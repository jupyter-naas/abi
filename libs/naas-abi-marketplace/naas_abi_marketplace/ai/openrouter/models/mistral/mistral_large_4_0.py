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


class MistralLarge40Model(ModelDefinition):
    CANONICAL_ID = "mistral-large-4-0"
    MODEL_ID = "mistralai/mistral-large-4-0"
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
        name="Mistral: Mistral Large 4",
        owner="mistralai",
        description="Mistral Large 4 is a frontier multimodal (text and image input) model from Mistral AI built for reasoning, coding, and agentic workloads. It offers a 1M-token context window with up...",
        canonical_slug="mistralai/mistral-large-4-0-20261006",
        hugging_face_id="mistralai/Mistral-Large-4-1T-A52B",
        created_at=datetime.fromtimestamp(1791294122),
        pricing={'prompt': '0.0000007', 'completion': '0.0000021', 'input_cache_read': '0.00000007'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 262144, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MistralLarge40Model.model
