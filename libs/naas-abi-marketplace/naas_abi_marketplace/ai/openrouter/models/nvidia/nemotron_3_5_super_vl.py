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


class Nemotron35SuperVlModel(ModelDefinition):
    CANONICAL_ID = "nemotron-3.5-super-vl"
    MODEL_ID = "nvidia/nemotron-3.5-super-vl"
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
        name="NVIDIA: Nemotron 3.5 Super VL",
        owner="nvidia",
        description="NVIDIA Nemotron 3.5 Super VL is an open multimodal mixture-of-experts model from NVIDIA, with 12B active parameters out of 120B total. It takes text, images, documents, GUI screenshots, and video...",
        canonical_slug="nvidia/nemotron-3.5-super-vl-20261015",
        hugging_face_id="nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16",
        created_at=datetime.fromtimestamp(1792076662),
        pricing={'prompt': '0.00000015', 'completion': '0.0000005', 'input_cache_read': '0.00000002'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Nemotron35SuperVlModel.model
