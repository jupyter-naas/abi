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


class Ministral14b2512Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.MINISTRAL_14B_2512
    MODEL_ID = "mistralai/ministral-14b-2512"
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
        context_window=262144,
        name="Mistral: Ministral 3 14B 2512",
        owner="mistralai",
        description="The largest model in the Ministral 3 family, Ministral 3 14B offers frontier capabilities and performance comparable to its larger Mistral Small 3.2 24B counterpart. A powerful and efficient language...",
        canonical_slug="mistralai/ministral-14b-2512",
        hugging_face_id="mistralai/Ministral-3-14B-Instruct-2512",
        created_at=datetime.fromtimestamp(1764681735),
        pricing={'prompt': '0.0000002', 'completion': '0.0000002', 'input_cache_read': '0.00000002'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logprobs', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 0.3, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Ministral14b2512Model.model
