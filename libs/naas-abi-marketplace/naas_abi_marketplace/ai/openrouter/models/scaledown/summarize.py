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


class SummarizeModel(ModelDefinition):
    CANONICAL_ID = "summarize"
    MODEL_ID = "scaledown/summarize"
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
        context_window=1000000,
        name="ScaleDown: Summarize",
        owner="scaledown",
        description="Summarize is an abstractive summarization model from ScaleDown. It condenses long text and documents into a fluent, faithful rewrite rather than lifting sentences from the source, and is suited for...",
        canonical_slug="scaledown/summarize-20260928",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1791893360),
        pricing={'prompt': '0.00000004', 'completion': '0'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 4000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['max_tokens'],
        default_parameters={},
    )


model: ChatModel = SummarizeModel.model
