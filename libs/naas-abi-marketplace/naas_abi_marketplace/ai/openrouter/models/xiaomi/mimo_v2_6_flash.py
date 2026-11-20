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


class MimoV26FlashModel(ModelDefinition):
    CANONICAL_ID = "mimo-v2.6-flash"
    MODEL_ID = "xiaomi/mimo-v2.6-flash"
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
        context_window=1050000,
        name="Xiaomi: MiMo-V2.6-Flash",
        owner="xiaomi",
        description="MiMo-V2.6-Flash is an open-source foundation model developed by Xiaomi. Built on a Mixture-of-Experts architecture with 309B total parameters and 15B activated per token, it employs a hybrid attention mechanism for...",
        canonical_slug="xiaomi/mimo-v2.6-flash-20260921",
        hugging_face_id="XiaomiMiMo/MiMo-V2.6-Flash-RL",
        created_at=datetime.fromtimestamp(1790021264),
        pricing={'prompt': '0.00000014', 'completion': '0.00000028', 'input_cache_read': '0.0000000028'},
        architecture={'modality': 'text+image+audio+video->text', 'input_modalities': ['text', 'image', 'video', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'parallel_tool_calls', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'frequency_penalty': 0},
    )


model: ChatModel = MimoV26FlashModel.model
