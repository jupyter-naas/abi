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


class DeepseekV41Flash1017BatchModel(ModelDefinition):
    CANONICAL_ID = "deepseek-v4.1-flash-1017:batch"
    MODEL_ID = "deepseek/deepseek-v4.1-flash-1017:batch"
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
        name="DeepSeek: DeepSeek V4.1 Flash 1017 (batch)",
        owner="deepseek",
        description="DeepSeek V4.1 Flash 1017 is the October 17, 2026 snapshot of DeepSeek V4.1 Flash, served by DeepSeek under the `deepseek-flash` API model name. V4.1 Flash is a sparse mixture-of-experts model...",
        canonical_slug="deepseek/deepseek-v4.1-flash-20261017",
        hugging_face_id="deepseek-ai/DeepSeek-V4.1-Flash-1017",
        created_at=datetime.fromtimestamp(1792225624),
        pricing={'prompt': '0.000000036', 'completion': '0.00000015', 'input_cache_read': '0.000000003'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'DeepSeek', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = DeepseekV41Flash1017BatchModel.model
