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


class AionRpLlama318bModel(ModelDefinition):
    CANONICAL_ID = "aion-rp-llama-3.1-8b"
    MODEL_ID = "aion-labs/aion-rp-llama-3.1-8b"
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
        context_window=32768,
        name="AionLabs: Aion-RP 1.0 (8B)",
        owner="aion-labs",
        description="Aion-RP-Llama-3.1-8B ranks the highest in the character evaluation portion of the RPBench-Auto benchmark, a roleplaying-specific variant of Arena-Hard-Auto, where LLMs evaluate each other’s responses. It is a fine-tuned base model...",
        canonical_slug="aion-labs/aion-rp-llama-3.1-8b",
        hugging_face_id="aion-labs/Aion-RP-Llama-3.1-8B",
        created_at=datetime.fromtimestamp(1738696718),
        pricing={'prompt': '0.0000008', 'completion': '0.0000016'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 32768, 'max_completion_tokens': 29491, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'temperature', 'top_p'],
        default_parameters={},
    )


model: ChatModel = AionRpLlama318bModel.model
