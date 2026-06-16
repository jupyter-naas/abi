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


class O1ProModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.O1_PRO
    MODEL_ID = "openai/o1-pro"
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
        name="OpenAI: o1-pro",
        owner="openai",
        description="The o1 series of models are trained with reinforcement learning to think before they answer and perform complex reasoning. The o1-pro model uses more compute to think harder and provide...",
        canonical_slug="openai/o1-pro",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1742423211),
        pricing={'prompt': '0.00015', 'completion': '0.0006', 'web_search': '0.01'},
        architecture={'modality': 'text+image+file->text', 'input_modalities': ['text', 'image', 'file'], 'output_modalities': ['text'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 200000, 'max_completion_tokens': 100000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'seed', 'structured_outputs'],
        default_parameters={},
    )


model: ChatModel = O1ProModel.model
