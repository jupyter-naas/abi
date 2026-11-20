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


class GptAstraLatestModel(ModelDefinition):
    CANONICAL_ID = "gpt-astra-latest"
    MODEL_ID = "~openai/gpt-astra-latest"
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
        name="OpenAI: GPT Astra Latest",
        owner="~openai",
        description="This model always redirects to the latest model in the GPT Astra family.",
        canonical_slug="~openai/gpt-astra-latest",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1789130932),
        pricing={'prompt': '0.000008', 'completion': '0.00004', 'web_search': '0.01', 'input_cache_read': '0.0000004', 'input_cache_write': '0.00001', 'overrides': [{'min_prompt_tokens': 272000, 'prompt': '0.000016', 'completion': '0.00006', 'input_cache_read': '0.0000008', 'input_cache_write': '0.00002'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['file', 'image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'Router', 'instruct_type': None},
        top_provider={'context_length': 1050000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_completion_tokens', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools', 'verbosity'],
        default_parameters={},
    )


model: ChatModel = GptAstraLatestModel.model
