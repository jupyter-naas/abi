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


class KimiK3BatchModel(ModelDefinition):
    CANONICAL_ID = "kimi-k3:batch"
    MODEL_ID = "moonshotai/kimi-k3:batch"
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
        name="MoonshotAI: Kimi K3 (batch)",
        owner="moonshotai",
        description="Kimi K3 is a 2.8T parameter open-weight multimodal reasoning model from Moonshot AI. It is suited for complex coding, knowledge work, and long-horizon agentic workflows, and is particularly strong at...",
        canonical_slug="moonshotai/kimi-k3-20260715",
        hugging_face_id="moonshotai/Kimi-K3",
        created_at=datetime.fromtimestamp(1784215858),
        pricing={'prompt': '0.00000228', 'completion': '0.0000114', 'input_cache_read': '0.000000228'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 16384, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': None, 'top_p': 0.95, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = KimiK3BatchModel.model
