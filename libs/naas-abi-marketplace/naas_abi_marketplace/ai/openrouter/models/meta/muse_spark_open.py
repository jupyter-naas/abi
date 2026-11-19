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


class MuseSparkOpenModel(ModelDefinition):
    CANONICAL_ID = "muse-spark-open"
    MODEL_ID = "meta/muse-spark-open"
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
        name="Meta: Muse Spark Open",
        owner="meta",
        description="Muse Spark Open is a coding-optimized open-weight model. Trained specifically for agentic coding workflows, it delivers higher first-attempt accuracy, reliable tool calling, and deep codebase understanding across the repos developers...",
        canonical_slug="meta/muse-spark-open-20261015",
        hugging_face_id="meta-models/Muse-Spark-Open-816B-A42B",
        created_at=datetime.fromtimestamp(1792087069),
        pricing={'prompt': '0.00000125', 'completion': '0.00000425', 'input_cache_read': '0.00000015'},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['text', 'image', 'video', 'file', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MuseSparkOpenModel.model
