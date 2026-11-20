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


class Ember1Model(ModelDefinition):
    CANONICAL_ID = "ember-1"
    MODEL_ID = "fireworks/ember-1"
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
        name="Fireworks: Ember-1",
        owner="fireworks",
        description="Ember-1 is a specialized reasoning model from Fireworks Research, built on [Kimi K3](https://openrouter.ai/moonshotai/kimi-k3). It is designed to make every token go further: it produces shorter reasoning traces, using roughly 40%...",
        canonical_slug="fireworks/ember-1-20260923",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1790208461),
        pricing={'prompt': '0.000003', 'completion': '0.000015', 'input_cache_read': '0.0000003'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Ember1Model.model
