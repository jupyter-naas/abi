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


class Gpt6LunaBatchModel(ModelDefinition):
    CANONICAL_ID = "gpt-6-luna:batch"
    MODEL_ID = "openai/gpt-6-luna:batch"
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
        name="OpenAI: GPT-6 Luna (batch)",
        owner="openai",
        description="GPT-6 Luna is the fast, cost-efficient model in OpenAI's GPT-6 series, positioned below GPT-6 Sol. It is suited for high-volume and latency-sensitive workloads such as chat, classification, and lightweight agentic...",
        canonical_slug="openai/gpt-6-luna-20260922",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1790100786),
        pricing={'prompt': '0.00000005', 'completion': '0.00000025', 'web_search': '0.01', 'input_cache_read': '0.000000005', 'input_cache_write': '0.0000000625', 'overrides': [{'min_prompt_tokens': 272000, 'prompt': '0.0000001', 'completion': '0.000000375', 'input_cache_read': '0.00000001', 'input_cache_write': '0.000000125'}]},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['file', 'image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 1050000, 'max_completion_tokens': 128000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'structured_outputs', 'tool_choice', 'tools', 'verbosity'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Gpt6LunaBatchModel.model
