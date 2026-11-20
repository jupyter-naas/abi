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


class MythomaxL213bModel(ModelDefinition):
    CANONICAL_ID = "mythomax-l2-13b"
    MODEL_ID = "gryphe/mythomax-l2-13b"
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
        name="MythoMax 13B",
        owner="gryphe",
        description="One of the highest performing and most popular fine-tunes of Llama 2 13B, with rich descriptions and roleplay. #merge",
        canonical_slug="gryphe/mythomax-l2-13b",
        hugging_face_id="Gryphe/MythoMax-L2-13b",
        created_at=datetime.fromtimestamp(1688256000),
        pricing={'prompt': '0.00000008', 'completion': '0.00000011'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Llama2', 'instruct_type': 'alpaca'},
        top_provider={'context_length': 4096, 'max_completion_tokens': 3686, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_a', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MythomaxL213bModel.model
