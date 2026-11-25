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


class L31Euryale70bModel(ModelDefinition):
    CANONICAL_ID = "l3.1-euryale-70b"
    MODEL_ID = "sao10k/l3.1-euryale-70b"
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
        context_window=131072,
        name="Sao10K: Llama 3.1 Euryale 70B v2.2",
        owner="sao10k",
        description="Euryale L3.1 70B v2.2 is a model focused on creative roleplay from [Sao10k](https://ko-fi.com/sao10k). It is the successor of [Euryale L3 70B v2.1](/models/sao10k/l3-euryale-70b).",
        canonical_slug="sao10k/l3.1-euryale-70b",
        hugging_face_id="Sao10K/L3.1-70B-Euryale-v2.2",
        created_at=datetime.fromtimestamp(1724803200),
        pricing={'prompt': '0.00000085', 'completion': '0.00000085'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Llama3', 'instruct_type': 'llama3'},
        top_provider={'context_length': 131072, 'max_completion_tokens': 16384, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = L31Euryale70bModel.model
