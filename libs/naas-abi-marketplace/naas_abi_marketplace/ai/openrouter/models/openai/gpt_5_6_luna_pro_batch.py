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


class Gpt56LunaProBatchModel(ModelDefinition):
    CANONICAL_ID = "gpt-5.6-luna-pro:batch"
    MODEL_ID = "openai/gpt-5.6-luna-pro:batch"
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
        name="OpenAI: GPT-5.6 Luna Pro (batch)",
        owner="openai",
        description="GPT-5.6 Luna Pro is the same underlying model as [GPT-5.6 Luna](https://openrouter.ai/openai/gpt-5.6-luna), served with `reasoning.mode` set to `pro` for higher-quality responses on complex tasks. **Cost note:** pro mode spends far more...",
        canonical_slug="openai/gpt-5.6-luna-pro-20260709",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1783590867),
        pricing={'prompt': '0.0000001', 'completion': '0.0000006', 'web_search': '0.01', 'input_cache_read': '0.00000001', 'overrides': [{'min_prompt_tokens': 272000, 'prompt': '0.0000002', 'completion': '0.0000009', 'input_cache_read': '0.00000002'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['file', 'image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 1050000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools', 'verbosity'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Gpt56LunaProBatchModel.model
