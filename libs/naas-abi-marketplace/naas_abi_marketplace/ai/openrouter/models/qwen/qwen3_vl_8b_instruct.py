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


class Qwen3Vl8bInstructModel(ModelDefinition):
    CANONICAL_ID = "qwen3-vl-8b-instruct"
    MODEL_ID = "qwen/qwen3-vl-8b-instruct"
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
        name="Qwen: Qwen3 VL 8B Instruct",
        owner="qwen",
        description="Qwen3-VL-8B-Instruct is a multimodal vision-language model from the Qwen3-VL series, built for high-fidelity understanding and reasoning across text, images, and video. It features improved multimodal fusion with Interleaved-MRoPE for long-horizon...",
        canonical_slug="qwen/qwen3-vl-8b-instruct",
        hugging_face_id="Qwen/Qwen3-VL-8B-Instruct",
        created_at=datetime.fromtimestamp(1760463308),
        pricing={'prompt': '0.00000025', 'completion': '0.00000075', 'input_cache_read': '0.00000012'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen3', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 0.7, 'top_p': 0.8, 'frequency_penalty': None},
    )


model: ChatModel = Qwen3Vl8bInstructModel.model
