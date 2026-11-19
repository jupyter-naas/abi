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


class Hy4PreviewModel(ModelDefinition):
    CANONICAL_ID = "hy4-preview"
    MODEL_ID = "tencent/hy4-preview"
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
        name="Tencent: Hy4 preview",
        owner="tencent",
        description="Tencent: Hy4 preview is a mixture-of-experts model from Tencent, with 49B active parameters out of 770B total. It is designed for coding agents, complex tool-use workflows, and productivity tasks that...",
        canonical_slug="tencent/hy4-preview-20260827",
        hugging_face_id="tencent/Hy4-preview",
        created_at=datetime.fromtimestamp(1787897375),
        pricing={'prompt': '0.0000007506', 'completion': '0.0000022509', 'input_cache_read': '0.0000000378', 'overrides': [{'utc_start': 0, 'utc_end': 1600, 'prompt': '0.000000834', 'completion': '0.000002501', 'input_cache_read': '0.000000042'}, {'utc_start': 1600, 'utc_end': 0, 'prompt': '0.0000007506', 'completion': '0.0000022509', 'input_cache_read': '0.0000000378'}]},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 64000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_completion_tokens', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Hy4PreviewModel.model
