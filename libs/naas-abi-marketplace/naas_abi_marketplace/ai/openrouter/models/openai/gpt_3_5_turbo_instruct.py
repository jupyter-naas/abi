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


class Gpt35TurboInstructModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_3_5_TURBO_INSTRUCT
    MODEL_ID = "openai/gpt-3.5-turbo-instruct"
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
        context_window=4095,
        name="GPT-3.5 Turbo Instruct",
        owner="openai",
        description="This model is a variant of GPT-3.5 Turbo tuned for instructional prompts and omitting chat-related optimizations. Training data: up to Sep 2021.",
        canonical_slug="openai/gpt-3.5-turbo-instruct",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1695859200),
        pricing={'prompt': '0.0000015', 'completion': '0.000002'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': 'chatml'},
        top_provider={'context_length': 4095, 'max_completion_tokens': 4096, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Gpt35TurboInstructModel.model
