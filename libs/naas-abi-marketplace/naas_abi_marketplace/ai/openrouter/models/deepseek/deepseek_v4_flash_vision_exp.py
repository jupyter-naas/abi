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


class DeepseekV4FlashVisionExpModel(ModelDefinition):
    CANONICAL_ID = "deepseek-v4-flash-vision-exp"
    MODEL_ID = "deepseek/deepseek-v4-flash-vision-exp"
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
        name="DeepSeek: DeepSeek V4 Flash Vision Exp",
        owner="deepseek",
        description="DeepSeek V4 Flash Vision Exp is an experimental vision-enabled version of [DeepSeek V4 Flash 0731](https://openrouter.ai/deepseek/deepseek-v4-flash-0731) from DeepSeek, adding image understanding while matching the base model on text capabilities including agents,...",
        canonical_slug="deepseek/deepseek-v4-flash-vision-exp-20260821",
        hugging_face_id="deepseek-ai/DeepSeek-V4-Flash-Vision-Exp",
        created_at=datetime.fromtimestamp(1787311563),
        pricing={'prompt': '0.00000044', 'completion': '0.00000132', 'input_cache_read': '0.000000014'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'DeepSeek', 'instruct_type': None},
        top_provider={'context_length': 1048575, 'max_completion_tokens': 943717, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = DeepseekV4FlashVisionExpModel.model
