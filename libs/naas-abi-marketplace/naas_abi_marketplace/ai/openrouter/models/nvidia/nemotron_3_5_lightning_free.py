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


class Nemotron35LightningFreeModel(ModelDefinition):
    CANONICAL_ID = "nemotron-3.5-lightning:free"
    MODEL_ID = "nvidia/nemotron-3.5-lightning:free"
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
        name="NVIDIA: Nemotron 3.5 Lightning (free)",
        owner="nvidia",
        description="NVIDIA Nemotron 3.5 Lightning is an open mixture-of-experts model from NVIDIA, with 3B active parameters out of 30B total. It is suited for high-throughput agentic workloads and specialized tasks that...",
        canonical_slug="nvidia/nemotron-3.5-lightning-20260807",
        hugging_face_id="nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
        created_at=datetime.fromtimestamp(1786452751),
        pricing={'prompt': '0', 'completion': '0'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'seed', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Nemotron35LightningFreeModel.model
