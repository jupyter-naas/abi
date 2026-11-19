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


class Motif3Model(ModelDefinition):
    CANONICAL_ID = "motif-3"
    MODEL_ID = "motif-technologies/motif-3"
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
        name="Motif Technologies: Motif 3",
        owner="motif-technologies",
        description="Motif 3 is a Mixture-of-Experts language model from Motif Technologies, with 314B total and 13.2B active parameters. It is a general-purpose multilingual model for English and Korean, particularly strong at...",
        canonical_slug="motif-technologies/motif-3",
        hugging_face_id="Motif-Technologies/Motif-3",
        created_at=datetime.fromtimestamp(1793655334),
        pricing={'prompt': '0.0000003', 'completion': '0.0000012', 'input_cache_read': '0.00000006'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Motif3Model.model
