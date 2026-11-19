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


class NexN26Model(ModelDefinition):
    CANONICAL_ID = "nex-n2.6"
    MODEL_ID = "nex-agi/nex-n2.6"
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
        context_window=262144,
        name="Nex AGI: Nex-N2.6",
        owner="nex-agi",
        description="Nex-N2.6 is an agentic model from Nex AGI, built on [GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash-BF16) with about 321B parameters. It is suited for computer use, coding, and long-horizon tasks that involve tools. Compared with...",
        canonical_slug="nex-agi/nex-n2.6-20261110",
        hugging_face_id="nex-agi/Nex-N2.6",
        created_at=datetime.fromtimestamp(1794282379),
        pricing={'prompt': '0.00000012', 'completion': '0.0000004', 'input_cache_read': '0.000000024'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'logprobs', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 0.7, 'top_p': 0.95, 'top_k': 40},
    )


model: ChatModel = NexN26Model.model
