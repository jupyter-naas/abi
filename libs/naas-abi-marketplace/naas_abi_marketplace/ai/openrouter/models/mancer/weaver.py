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


class WeaverModel(ModelDefinition):
    CANONICAL_ID = "weaver"
    MODEL_ID = "mancer/weaver"
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
        context_window=8000,
        name="Mancer: Weaver (alpha)",
        owner="mancer",
        description="An attempt to recreate Claude-style verbosity, but don't expect the same level of coherence or memory. Meant for use in roleplay/narrative situations.",
        canonical_slug="mancer/weaver",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1690934400),
        pricing={'prompt': '0.0000003', 'completion': '0.0000005', 'input_cache_read': '0.0000003'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Llama2', 'instruct_type': 'alpaca'},
        top_provider={'context_length': 8000, 'max_completion_tokens': 6000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'temperature', 'top_a', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = WeaverModel.model
