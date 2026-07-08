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


class VoxtralSmall24b2507Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.VOXTRAL_SMALL_24B_2507
    MODEL_ID = "mistralai/voxtral-small-24b-2507"
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
        context_window=32000,
        name="Voxtral Small 24B 2507",
        owner="mistralai",
        description="Voxtral Small is an enhancement of Mistral Small 3, incorporating state-of-the-art audio input capabilities while retaining best-in-class text performance. It excels at speech transcription, translation and audio understanding. Input audio...",
        canonical_slug="mistralai/voxtral-small-24b-2507",
        hugging_face_id="mistralai/Voxtral-Small-24B-2507",
        created_at=datetime.fromtimestamp(1761835144),
        pricing={'prompt': '0.0000001', 'completion': '0.0000003', 'audio': '0.0001', 'input_cache_read': '0.00000001'},
        architecture={'modality': 'text+file+audio->text', 'input_modalities': ['text', 'audio', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 32000, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 0.2, 'top_p': 0.95, 'frequency_penalty': None},
    )


model: ChatModel = VoxtralSmall24b2507Model.model
