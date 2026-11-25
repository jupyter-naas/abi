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


class Pareto2610PreviewModel(ModelDefinition):
    CANONICAL_ID = "pareto-26.10-preview"
    MODEL_ID = "unbiased/pareto-26.10-preview"
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
        name="Pareto 26.10 Preview",
        owner="unbiased",
        description="Pareto is a multimodal composite model built for research, coding, and agentic workflows, while delivering frontier-level performance across a broad range of general-purpose tasks. This is a preview of the...",
        canonical_slug="unbiased/pareto-26.10-preview-20260929",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1790863623),
        pricing={'prompt': '0.0000008', 'completion': '0.0000032', 'input_cache_read': '0.00000003'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'response_format', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Pareto2610PreviewModel.model
