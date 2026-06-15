from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Gpt4oSearchPreviewModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_4O_SEARCH_PREVIEW
    MODEL_ID = "openai/gpt-4o-search-preview"
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
        context_window=128000,
        name="OpenAI: GPT-4o Search Preview",
        owner="openai",
        description="GPT-4o Search Previewis a specialized model for web search in Chat Completions. It is trained to understand and execute web search queries.",
        canonical_slug="openai/gpt-4o-search-preview-2025-03-11",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1741817949),
        pricing={'prompt': '0.0000025', 'completion': '0.00001', 'web_search': '0.035'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 16384, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'response_format', 'structured_outputs', 'web_search_options'],
        default_parameters={},
    )


model: ChatModel = Gpt4oSearchPreviewModel.model
