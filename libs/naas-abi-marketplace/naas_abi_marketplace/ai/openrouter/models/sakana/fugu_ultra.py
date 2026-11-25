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


class FuguUltraModel(ModelDefinition):
    CANONICAL_ID = "fugu-ultra"
    MODEL_ID = "sakana/fugu-ultra"
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
        context_window=1000000,
        name="Sakana: Fugu Ultra",
        owner="sakana",
        description="Fugu Ultra is the higher-performance model in Sakana AI's Fugu family. Rather than a single monolithic model, Fugu is a learned multi-agent orchestration system: a language model trained to route...",
        canonical_slug="sakana/fugu-ultra-20260615",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1782276303),
        pricing={'prompt': '0.000005', 'completion': '0.00003', 'web_search': '0.01', 'input_cache_read': '0.0000005', 'overrides': [{'min_prompt_tokens': 272000, 'prompt': '0.00001', 'completion': '0.000045', 'input_cache_read': '0.000001'}]},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 128000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'reasoning', 'reasoning_effort', 'structured_outputs', 'tool_choice', 'tools', 'web_search_options'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = FuguUltraModel.model
