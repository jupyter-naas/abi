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


class MistralSmall24bInstruct2501Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.MISTRAL_SMALL_24B_INSTRUCT_2501
    MODEL_ID = "mistralai/mistral-small-24b-instruct-2501"
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
        context_window=32768,
        name="Mistral: Mistral Small 3",
        owner="mistralai",
        description="Mistral Small 3 is a 24B-parameter language model optimized for low-latency performance across common AI tasks. Released under the Apache 2.0 license, it features both pre-trained and instruction-tuned versions designed...",
        canonical_slug="mistralai/mistral-small-24b-instruct-2501",
        hugging_face_id="mistralai/Mistral-Small-24B-Instruct-2501",
        created_at=datetime.fromtimestamp(1738255409),
        pricing={'prompt': '0.00000005', 'completion': '0.00000008'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 32768, 'max_completion_tokens': 16384, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_k', 'top_p'],
        default_parameters={'temperature': 0.3, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = MistralSmall24bInstruct2501Model.model
