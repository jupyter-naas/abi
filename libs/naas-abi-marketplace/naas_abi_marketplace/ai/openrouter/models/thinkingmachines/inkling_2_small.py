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


class Inkling2SmallModel(ModelDefinition):
    CANONICAL_ID = "inkling-2-small"
    MODEL_ID = "thinkingmachines/inkling-2-small"
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
        name="Thinking Machines: Inkling 2 Small",
        owner="thinkingmachines",
        description="Inkling 2 Small is an open-weight multimodal mixture-of-experts reasoning model from Thinking Machines Lab, with 17B active parameters out of 594B total. It is the first model in the second...",
        canonical_slug="thinkingmachines/inkling-2-small-20261107",
        hugging_face_id="thinkingmachines/Inkling-2-Small",
        created_at=datetime.fromtimestamp(1794261847),
        pricing={'prompt': '0.0000003', 'completion': '0.000001', 'input_cache_read': '0.00000003'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Inkling2SmallModel.model
