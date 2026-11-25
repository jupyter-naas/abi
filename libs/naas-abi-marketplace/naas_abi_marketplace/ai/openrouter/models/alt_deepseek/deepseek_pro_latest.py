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


class DeepseekProLatestModel(ModelDefinition):
    CANONICAL_ID = "deepseek-pro-latest"
    MODEL_ID = "~deepseek/deepseek-pro-latest"
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
        name="DeepSeek: DeepSeek Pro Latest",
        owner="~deepseek",
        description="This model always redirects to the latest model in the DeepSeek Pro family.",
        canonical_slug="~deepseek/deepseek-pro-latest",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1789399174),
        pricing={'prompt': '0.0000001211', 'completion': '0.000008', 'input_cache_read': '0.00000012'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Router', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 393216, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 1},
    )


model: ChatModel = DeepseekProLatestModel.model
