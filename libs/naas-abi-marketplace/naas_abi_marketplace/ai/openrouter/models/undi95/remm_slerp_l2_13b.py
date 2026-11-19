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


class RemmSlerpL213bModel(ModelDefinition):
    CANONICAL_ID = "remm-slerp-l2-13b"
    MODEL_ID = "undi95/remm-slerp-l2-13b"
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
        context_window=6144,
        name="ReMM SLERP 13B",
        owner="undi95",
        description="A recreation trial of the original MythoMax-L2-B13 but with updated models. #merge",
        canonical_slug="undi95/remm-slerp-l2-13b",
        hugging_face_id="Undi95/ReMM-SLERP-L2-13B",
        created_at=datetime.fromtimestamp(1689984000),
        pricing={'prompt': '0.0000003', 'completion': '0.0000005', 'input_cache_read': '0.0000002'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Llama2', 'instruct_type': 'alpaca'},
        top_provider={'context_length': 6144, 'max_completion_tokens': 5529, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_a', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = RemmSlerpL213bModel.model
