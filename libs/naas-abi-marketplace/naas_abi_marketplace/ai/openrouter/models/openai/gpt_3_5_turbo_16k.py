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


class Gpt35Turbo16kModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_3_5_TURBO_16K
    MODEL_ID = "openai/gpt-3.5-turbo-16k"
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
        context_window=16385,
        name="OpenAI: GPT-3.5 Turbo 16k",
        owner="openai",
        description="This model offers four times the context length of gpt-3.5-turbo, allowing it to support approximately 20 pages of text in a single request at a higher cost. Training data: up...",
        canonical_slug="openai/gpt-3.5-turbo-16k",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1693180800),
        pricing={'prompt': '0.000003', 'completion': '0.000004'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 16385, 'max_completion_tokens': 4096, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_completion_tokens', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gpt35Turbo16kModel.model
