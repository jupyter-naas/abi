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


class Unslopnemo12bModel(ModelDefinition):
    CANONICAL_ID = "unslopnemo-12b"
    MODEL_ID = "thedrummer/unslopnemo-12b"
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
        context_window=1024000,
        name="TheDrummer: UnslopNemo 12B",
        owner="thedrummer",
        description="UnslopNemo v4.1 is the latest addition from the creator of Rocinante, designed for adventure writing and role-play scenarios.",
        canonical_slug="thedrummer/unslopnemo-12b",
        hugging_face_id="TheDrummer/UnslopNemo-12B-v4.1",
        created_at=datetime.fromtimestamp(1731103448),
        pricing={'prompt': '0.0000004', 'completion': '0.0000004'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': 'mistral'},
        top_provider={'context_length': 1024000, 'max_completion_tokens': 819200, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Unslopnemo12bModel.model
