from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class O4MiniDeepResearchModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.O4_MINI_DEEP_RESEARCH
    MODEL_ID = "openai/o4-mini-deep-research"
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
        context_window=200000,
        name="OpenAI: o4 Mini Deep Research",
        owner="openai",
        description="o4-mini-deep-research is OpenAI's faster, more affordable deep research model—ideal for tackling complex, multi-step research tasks.\n\nNote: This model always uses the 'web_search' tool which adds additional cost.",
        canonical_slug="openai/o4-mini-deep-research-2025-06-26",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1760129642),
        pricing={'prompt': '0.000002', 'completion': '0.000008', 'web_search': '0.01', 'input_cache_read': '0.0000005'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['file', 'image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 200000, 'max_completion_tokens': 100000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = O4MiniDeepResearchModel.model
