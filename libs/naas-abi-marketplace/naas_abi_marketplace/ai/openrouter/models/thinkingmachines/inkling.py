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


class InklingModel(ModelDefinition):
    CANONICAL_ID = "inkling"
    MODEL_ID = "thinkingmachines/inkling"
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
        context_window=524288,
        name="Thinking Machines: Inkling",
        owner="thinkingmachines",
        description="Inkling is an open-weight multimodal mixture-of-experts model from Thinking Machines Lab, with 41B active parameters out of 975B total. It is designed for general-purpose reasoning, coding, agentic and tool-use systems,...",
        canonical_slug="thinkingmachines/inkling-20260715",
        hugging_face_id="thinkingmachines/Inkling",
        created_at=datetime.fromtimestamp(1784325956),
        pricing={'prompt': '0.000001', 'completion': '0.00000405', 'input_cache_read': '0.00000017'},
        architecture={'modality': 'text+image+audio->text', 'input_modalities': ['text', 'image', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 524288, 'max_completion_tokens': 471859, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = InklingModel.model
