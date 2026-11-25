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


class DeepseekV41Flash1017Model(ModelDefinition):
    CANONICAL_ID = "deepseek-v4.1-flash-1017"
    MODEL_ID = "deepseek/deepseek-v4.1-flash-1017"
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
        name="DeepSeek: DeepSeek V4.1 Flash 1017",
        owner="deepseek",
        description="DeepSeek V4.1 Flash 1017 is the October 17, 2026 snapshot of DeepSeek V4.1 Flash, served by DeepSeek under the `deepseek-flash` API model name. V4.1 Flash is a sparse mixture-of-experts model...",
        canonical_slug="deepseek/deepseek-v4.1-flash-20261017",
        hugging_face_id="deepseek-ai/DeepSeek-V4.1-Flash-1017",
        created_at=datetime.fromtimestamp(1792225624),
        pricing={'prompt': '0.00000015', 'completion': '0.0000006', 'input_cache_read': '0.000000003', 'overrides': [{'utc_days': ['saturday', 'sunday'], 'prompt': '0.00000015', 'completion': '0.0000006', 'input_cache_read': '0.000000003'}, {'utc_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'], 'utc_start': 0, 'utc_end': 100, 'prompt': '0.00000015', 'completion': '0.0000006', 'input_cache_read': '0.000000003'}, {'utc_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'], 'utc_start': 100, 'utc_end': 400, 'prompt': '0.0000003', 'completion': '0.0000012', 'input_cache_read': '0.000000006'}, {'utc_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'], 'utc_start': 400, 'utc_end': 600, 'prompt': '0.00000015', 'completion': '0.0000006', 'input_cache_read': '0.000000003'}, {'utc_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'], 'utc_start': 600, 'utc_end': 1000, 'prompt': '0.0000003', 'completion': '0.0000012', 'input_cache_read': '0.000000006'}, {'utc_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'], 'utc_start': 1000, 'utc_end': 0, 'prompt': '0.00000015', 'completion': '0.0000006', 'input_cache_read': '0.000000003'}]},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'DeepSeek', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 393216, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_completion_tokens', 'max_tokens', 'min_p', 'parallel_tool_calls', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = DeepseekV41Flash1017Model.model
