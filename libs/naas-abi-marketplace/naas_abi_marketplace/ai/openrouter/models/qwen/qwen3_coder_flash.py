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


class Qwen3CoderFlashModel(ModelDefinition):
    CANONICAL_ID = "qwen3-coder-flash"
    MODEL_ID = "qwen/qwen3-coder-flash"
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
        name="Qwen: Qwen3 Coder Flash",
        owner="qwen",
        description="Qwen3 Coder Flash is Alibaba's fast and cost efficient version of their proprietary Qwen3 Coder Plus. It is a powerful coding agent model specializing in autonomous programming via tool calling...",
        canonical_slug="qwen/qwen3-coder-flash",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1758115536),
        pricing={'prompt': '0.000000195', 'completion': '0.000000975', 'input_cache_read': '0.000000039', 'input_cache_write': '0.00000024375', 'overrides': [{'min_prompt_tokens': 32000, 'prompt': '0.000000325', 'completion': '0.000001625', 'input_cache_read': '0.000000065', 'input_cache_write': '0.00000040625'}, {'min_prompt_tokens': 128000, 'prompt': '0.00000052', 'completion': '0.0000026', 'input_cache_read': '0.000000104', 'input_cache_write': '0.00000065'}]},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen3', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logprobs', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Qwen3CoderFlashModel.model
