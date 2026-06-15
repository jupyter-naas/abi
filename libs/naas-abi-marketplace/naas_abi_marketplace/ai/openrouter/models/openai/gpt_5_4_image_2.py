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


class Gpt54Image2Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_5_4_IMAGE_2
    MODEL_ID = "openai/gpt-5.4-image-2"
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
        context_window=272000,
        name="OpenAI: GPT-5.4 Image 2",
        owner="openai",
        description="[GPT-5.4](https://openrouter.ai/openai/gpt-5.4) Image 2 combines OpenAI's GPT-5.4 model with state-of-the-art image generation capabilities from GPT Image 2. It enables rich multimodal workflows, allowing users to seamlessly move between reasoning, coding, and...",
        canonical_slug="openai/gpt-5.4-image-2-20260421",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1776797528),
        pricing={'prompt': '0.000008', 'completion': '0.000015', 'web_search': '0.01', 'input_cache_read': '0.000002'},
        architecture={'modality': 'text+image+file->text+image', 'input_modalities': ['image', 'text', 'file'], 'output_modalities': ['image', 'text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 272000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'top_logprobs'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Gpt54Image2Model.model
