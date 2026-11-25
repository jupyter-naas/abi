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


class DeepseekV4Flash0731BatchModel(ModelDefinition):
    CANONICAL_ID = "deepseek-v4-flash-0731:batch"
    MODEL_ID = "deepseek/deepseek-v4-flash-0731:batch"
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
        name="DeepSeek: DeepSeek V4 Flash 0731 (batch)",
        owner="deepseek",
        description="DeepSeek V4 Flash 0731 is a sparse mixture-of-experts model from DeepSeek, with 13B active parameters out of 284B total. This re-post-trained revision is suited for coding, reasoning, and agent workflows....",
        canonical_slug="deepseek/deepseek-v4-flash-20260731",
        hugging_face_id="deepseek-ai/DeepSeek-V4-Flash-0731",
        created_at=datetime.fromtimestamp(1785478908),
        pricing={'prompt': '0.000000048', 'completion': '0.000000144', 'input_cache_read': '0.000000012'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'DeepSeek', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 384000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = DeepseekV4Flash0731BatchModel.model
