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


class RekaEdgeModel(ModelDefinition):
    CANONICAL_ID = "reka-edge"
    MODEL_ID = "rekaai/reka-edge"
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
        context_window=16384,
        name="Reka Edge",
        owner="rekaai",
        description="Reka Edge is an extremely efficient 7B multimodal vision-language model that accepts image/video+text inputs and generates text outputs. This model is optimized specifically to deliver industry-leading performance in image understanding,...",
        canonical_slug="rekaai/reka-edge-2603",
        hugging_face_id="RekaAI/reka-edge-2603",
        created_at=datetime.fromtimestamp(1774026965),
        pricing={'prompt': '0.0000001', 'completion': '0.0000001'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['image', 'text', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 16384, 'max_completion_tokens': 14745, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logprobs', 'max_tokens', 'presence_penalty', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = RekaEdgeModel.model
