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


class Lfm2524bA2bModel(ModelDefinition):
    CANONICAL_ID = "lfm-2.5-24b-a2b"
    MODEL_ID = "liquid/lfm-2.5-24b-a2b"
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
        context_window=128000,
        name="LiquidAI: LFM2.5-24B-A2B",
        owner="liquid",
        description="LFM2.5-24B-A2B is a mixture-of-experts reasoning model from Liquid AI with 24B total and 2.45B active parameters. It always reasons before answering and is built for agents that call tools. Liquid...",
        canonical_slug="liquid/lfm-2.5-24b-a2b-20261012",
        hugging_face_id="LiquidAI/LFM2.5-24B-A2B",
        created_at=datetime.fromtimestamp(1791912025),
        pricing={'prompt': '0.00000005', 'completion': '0.0000007', 'input_cache_read': '0.000000025'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 8192, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_completion_tokens', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 0.1, 'top_k': 50, 'repetition_penalty': 1.05},
    )


model: ChatModel = Lfm2524bA2bModel.model
