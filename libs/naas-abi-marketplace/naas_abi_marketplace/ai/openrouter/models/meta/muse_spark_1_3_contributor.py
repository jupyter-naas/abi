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


class MuseSpark13ContributorModel(ModelDefinition):
    CANONICAL_ID = "muse-spark-1.3-contributor"
    MODEL_ID = "meta/muse-spark-1.3-contributor"
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
        name="Meta: Muse Spark 1.3 Contributor",
        owner="meta",
        description="Muse Spark 1.3 Contributor is the cost-efficient contributor tier of Meta’s multimodal reasoning model for experimentation, learning, and early-stage agentic, multi-agent, and coding workflows. It is designed to track information...",
        canonical_slug="meta/muse-spark-1.3-contributor-20260902",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1788381519),
        pricing={'prompt': '0.0000001', 'completion': '0.0000002', 'web_search': '0.0025', 'input_cache_read': '0.000000002'},
        architecture={'modality': 'text+image+file+video->text', 'input_modalities': ['text', 'image', 'video', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MuseSpark13ContributorModel.model
