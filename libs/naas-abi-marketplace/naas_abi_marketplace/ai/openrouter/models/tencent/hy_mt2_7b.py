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


class HyMt27bModel(ModelDefinition):
    CANONICAL_ID = "hy-mt2-7b"
    MODEL_ID = "tencent/hy-mt2-7b"
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
        context_window=8192,
        name="Tencent: Hy-MT2-7B",
        owner="tencent",
        description="Hy-MT2-7B is a 7B-parameter translation model from Tencent. It supports 33 language pairs and five Chinese dialect and minority-language pairs, with workflows for structured, delimiter-based, contextual, glossary-based, and style-guided translation.",
        canonical_slug="tencent/hy-mt2-7b-20260521",
        hugging_face_id="tencent/Hy-MT2-7B",
        created_at=datetime.fromtimestamp(1787148797),
        pricing={'prompt': '0.000000074', 'completion': '0.000000295'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 8192, 'max_completion_tokens': 4096, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['max_completion_tokens', 'max_tokens', 'response_format', 'stop', 'structured_outputs', 'temperature'],
        default_parameters={},
    )


model: ChatModel = HyMt27bModel.model
