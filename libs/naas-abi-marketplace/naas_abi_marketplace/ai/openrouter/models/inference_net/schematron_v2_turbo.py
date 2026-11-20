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


class SchematronV2TurboModel(ModelDefinition):
    CANONICAL_ID = "schematron-v2-turbo"
    MODEL_ID = "inference-net/schematron-v2-turbo"
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
        name="Inference.net: Schematron V2 Turbo",
        owner="inference-net",
        description="Schematron V2 Turbo is a 3B-parameter HTML-to-JSON extraction model from Inference.net. It prioritizes throughput for high-volume extraction workloads. Extraction instructions must be supplied through a JSON schema in response_format rather...",
        canonical_slug="inference-net/schematron-v2-turbo-20260902",
        hugging_face_id="inference-net/schematron-v2-granite-4.0-h-micro",
        created_at=datetime.fromtimestamp(1789176949),
        pricing={'prompt': '0.00000003', 'completion': '0.00000015', 'input_cache_read': '0.00000003'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 8192, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = SchematronV2TurboModel.model
