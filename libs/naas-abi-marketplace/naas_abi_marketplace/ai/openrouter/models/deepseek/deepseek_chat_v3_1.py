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


class DeepseekChatV31Model(ModelDefinition):
    CANONICAL_ID = "deepseek-chat-v3.1"
    MODEL_ID = "deepseek/deepseek-chat-v3.1"
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
        context_window=163840,
        name="DeepSeek: DeepSeek V3.1",
        owner="deepseek",
        description="DeepSeek-V3.1 is a large hybrid reasoning model (671B parameters, 37B active) that supports both thinking and non-thinking modes via prompt templates. It extends the DeepSeek-V3 base with a two-phase long-context...",
        canonical_slug="deepseek/deepseek-chat-v3.1",
        hugging_face_id="deepseek-ai/DeepSeek-V3.1",
        created_at=datetime.fromtimestamp(1755779628),
        pricing={'prompt': '0.00000025', 'completion': '0.00000095', 'input_cache_read': '0.00000013'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'DeepSeek', 'instruct_type': 'deepseek-v3.1'},
        top_provider={'context_length': 163840, 'max_completion_tokens': 147456, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = DeepseekChatV31Model.model
