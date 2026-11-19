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


class PerceptronMk15Model(ModelDefinition):
    CANONICAL_ID = "perceptron-mk1.5"
    MODEL_ID = "perceptron/perceptron-mk1.5"
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
        context_window=36864,
        name="Perceptron: Perceptron Mk1.5",
        owner="perceptron",
        description="Perceptron Mk1.5 is Perceptron's embodied reasoning model for physical agents. It accepts text, image, video, and audio input, and answers with text plus optional structured annotations: points, boxes, polygons, tracks,...",
        canonical_slug="perceptron/perceptron-mk1.5-20260925",
        hugging_face_id=None,
        created_at=datetime.fromtimestamp(1790352661),
        pricing={'prompt': '0.00000015', 'completion': '0.0000015'},
        architecture={'modality': 'text+image+audio+video->text', 'input_modalities': ['text', 'image', 'video', 'audio'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 36864, 'max_completion_tokens': 8192, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'reasoning_effort', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = PerceptronMk15Model.model
