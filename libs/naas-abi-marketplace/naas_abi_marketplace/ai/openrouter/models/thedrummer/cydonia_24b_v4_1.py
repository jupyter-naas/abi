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


class Cydonia24bV41Model(ModelDefinition):
    CANONICAL_ID = "cydonia-24b-v4.1"
    MODEL_ID = "thedrummer/cydonia-24b-v4.1"
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
        name="TheDrummer: Cydonia 24B V4.1",
        owner="thedrummer",
        description="Uncensored and creative writing model based on Mistral Small 3.2 24B with good recall, prompt adherence, and intelligence.",
        canonical_slug="thedrummer/cydonia-24b-v4.1",
        hugging_face_id="thedrummer/cydonia-24b-v4.1",
        created_at=datetime.fromtimestamp(1758931878),
        pricing={'prompt': '0.0000003', 'completion': '0.0000005', 'input_cache_read': '0.00000015'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 131072, 'max_completion_tokens': 117964, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Cydonia24bV41Model.model
