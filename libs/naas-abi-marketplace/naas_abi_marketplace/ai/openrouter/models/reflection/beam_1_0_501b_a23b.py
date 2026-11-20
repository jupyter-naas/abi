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


class Beam10501bA23bModel(ModelDefinition):
    CANONICAL_ID = "beam-1.0-501b-a23b"
    MODEL_ID = "reflection/beam-1.0-501b-a23b"
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
        name="Reflection: Beam 1.0 501B A23B",
        owner="reflection",
        description="Beam 1.0 is Reflection's open-weight reasoning model for coding and long-horizon agentic workflows. It uses a sparse mixture-of-experts architecture with 501B total and 23B active parameters per token, and a...",
        canonical_slug="reflection/beam-1.0-501b-a23b-20261016",
        hugging_face_id="reflection/Beam-1.0-501B-A23B",
        created_at=datetime.fromtimestamp(1792160499),
        pricing={'prompt': '0.00000025', 'completion': '0.000001', 'input_cache_read': '0.00000005'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Beam10501bA23bModel.model
