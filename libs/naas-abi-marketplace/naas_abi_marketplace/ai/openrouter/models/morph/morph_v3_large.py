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


class MorphV3LargeModel(ModelDefinition):
    CANONICAL_ID = "morph-v3-large"
    MODEL_ID = "morph/morph-v3-large"
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
        name="Morph: Morph V3 Large",
        owner="morph",
        description="Morph's high-accuracy apply model for complex code edits. ~4,500 tokens/sec with 98% accuracy for precise code transformations. The model requires the prompt to be in the following format: <instruction>{instruction}</instruction> <code>{initial_code}</code>...",
        canonical_slug="morph/morph-v3-large",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1751910858),
        pricing={'prompt': '0.0000009', 'completion': '0.0000019'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 131072, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['logprobs', 'max_tokens', 'response_format', 'stop', 'structured_outputs', 'temperature', 'top_logprobs'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = MorphV3LargeModel.model
