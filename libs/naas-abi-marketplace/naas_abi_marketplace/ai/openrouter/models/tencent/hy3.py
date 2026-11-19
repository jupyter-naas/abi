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


class Hy3Model(ModelDefinition):
    CANONICAL_ID = "hy3"
    MODEL_ID = "tencent/hy3"
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
        name="Tencent: Hy3",
        owner="tencent",
        description="Hy3 is a 295B-parameter Mixture-of-Experts model from Tencent (21B active, 192 experts with top-8 routing) built for reasoning, agentic workflows, and real-world production use. It supports a configurable reasoning effort:...",
        canonical_slug="tencent/hy3-20260706",
        hugging_face_id="tencent/Hy3",
        created_at=datetime.fromtimestamp(1783344048),
        pricing={'prompt': '0.0000000825', 'completion': '0.00000033', 'input_cache_read': '0.000000020625', 'overrides': [{'utc_start': 0, 'utc_end': 1600, 'prompt': '0.000000132', 'completion': '0.000000528', 'input_cache_read': '0.000000033'}, {'utc_start': 1600, 'utc_end': 0, 'prompt': '0.0000000825', 'completion': '0.00000033', 'input_cache_read': '0.000000020625'}]},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 128000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_completion_tokens', 'max_tokens', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': 0.9, 'top_p': 1, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Hy3Model.model
