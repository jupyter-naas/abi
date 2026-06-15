from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Gpt4TurboPreviewModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_4_TURBO_PREVIEW
    MODEL_ID = "openai/gpt-4-turbo-preview"
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
        context_window=128000,
        name="OpenAI: GPT-4 Turbo Preview",
        owner="openai",
        description="The preview GPT-4 model with improved instruction following, JSON mode, reproducible outputs, parallel function calling, and more. Training data: up to Dec 2023. **Note:** heavily rate limited by OpenAI while...",
        canonical_slug="openai/gpt-4-turbo-preview",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1706140800),
        pricing={'prompt': '0.00001', 'completion': '0.00003'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 4096, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gpt4TurboPreviewModel.model
