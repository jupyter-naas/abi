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


class Qwen3Vl235bA22bInstructModel(ModelDefinition):
    CANONICAL_ID = "qwen3-vl-235b-a22b-instruct"
    MODEL_ID = "qwen/qwen3-vl-235b-a22b-instruct"
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
        name="Qwen: Qwen3 VL 235B A22B Instruct",
        owner="qwen",
        description="Qwen3-VL-235B-A22B Instruct is an open-weight multimodal model that unifies strong text generation with visual understanding across images and video. The Instruct model targets general vision-language use (VQA, document parsing, chart/table...",
        canonical_slug="qwen/qwen3-vl-235b-a22b-instruct",
        hugging_face_id="Qwen/Qwen3-VL-235B-A22B-Instruct",
        created_at=datetime.fromtimestamp(1758668687),
        pricing={'prompt': '0.00000021', 'completion': '0.0000019', 'input_cache_read': '0.0000001'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Qwen3', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 32768, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 0.7, 'top_p': 0.8, 'frequency_penalty': None},
    )


model: ChatModel = Qwen3Vl235bA22bInstructModel.model
