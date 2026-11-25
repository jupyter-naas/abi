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


class MuseSpark13Model(ModelDefinition):
    CANONICAL_ID = "muse-spark-1.3"
    MODEL_ID = "meta/muse-spark-1.3"
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
        name="Meta: Muse Spark 1.3",
        owner="meta",
        description="Muse Spark 1.3 is a multimodal reasoning model from Meta for long-running agentic, multi-agent, and coding workflows. It is designed to keep track of information across extended tasks, work through...",
        canonical_slug="meta/muse-spark-1.3-20260902",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1788378359),
        pricing={'prompt': '0.00000125', 'completion': '0.00000425', 'web_search': '0.0025', 'input_cache_read': '0.00000015'},
        architecture={'modality': 'text+image+file+video->text', 'input_modalities': ['text', 'image', 'video', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MuseSpark13Model.model
