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


class Gpt5ImageModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_5_IMAGE
    MODEL_ID = "openai/gpt-5-image"
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
        context_window=400000,
        name="OpenAI: GPT-5 Image",
        owner="openai",
        description="[GPT-5](https://openrouter.ai/openai/gpt-5) Image combines OpenAI's GPT-5 model with state-of-the-art image generation capabilities. It offers major improvements in reasoning, code quality, and user experience while incorporating GPT Image 1's superior instruction following,...",
        canonical_slug="openai/gpt-5-image",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1760447986),
        pricing={'prompt': '0.00001', 'completion': '0.00001', 'web_search': '0.01', 'input_cache_read': '0.00000125'},
        architecture={'modality': 'text+image+file->text+image', 'input_modalities': ['image', 'text', 'file'], 'output_modalities': ['image', 'text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 400000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Gpt5ImageModel.model
