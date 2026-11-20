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


class Qwen37FlashModel(ModelDefinition):
    CANONICAL_ID = "qwen3.7-flash"
    MODEL_ID = "qwen/qwen3.7-flash"
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
        context_window=1000000,
        name="Qwen: Qwen3.7 Flash",
        owner="qwen",
        description="Qwen3.7 Flash is a vision-language reasoning model from Alibaba. It is suited for multimodal agents, visual coding, search, and computer interaction, with strengths in object recognition, spatial understanding, and real-world...",
        canonical_slug="qwen/qwen3.7-flash-20260727",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1785190561),
        pricing={'prompt': '0.00000003', 'completion': '0.00000013', 'input_cache_read': '0.000000006', 'input_cache_write': '0.000000038', 'overrides': [{'min_prompt_tokens': 32000, 'prompt': '0.0000001', 'completion': '0.0000004', 'input_cache_read': '0.00000002', 'input_cache_write': '0.000000125'}, {'min_prompt_tokens': 256000, 'prompt': '0.0000002', 'completion': '0.0000008', 'input_cache_read': '0.00000004', 'input_cache_write': '0.00000025'}]},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Qwen37FlashModel.model
