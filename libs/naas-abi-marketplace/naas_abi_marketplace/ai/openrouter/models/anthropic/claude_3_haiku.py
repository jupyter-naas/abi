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


class Claude3HaikuModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_3_HAIKU
    MODEL_ID = "anthropic/claude-3-haiku"
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
        context_window=200000,
        name="3 Haiku",
        owner="anthropic",
        description="Claude 3 Haiku is Anthropic's fastest and most compact model for\nnear-instant responsiveness. Quick and accurate targeted performance.\n\nSee the launch announcement and benchmark results [here](https://www.anthropic.com/news/claude-3-haiku)\n\n#multimodal",
        canonical_slug="anthropic/claude-3-haiku",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1710288000),
        pricing={'prompt': '0.00000025', 'completion': '0.00000125', 'web_search': '0.01', 'input_cache_read': '0.00000003', 'input_cache_write': '0.0000003'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Claude', 'instruct_type': None},
        top_provider={'context_length': 200000, 'max_completion_tokens': 4096, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Claude3HaikuModel.model
