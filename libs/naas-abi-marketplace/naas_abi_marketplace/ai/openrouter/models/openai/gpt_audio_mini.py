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


class GptAudioMiniModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_AUDIO_MINI
    MODEL_ID = "openai/gpt-audio-mini"
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
        context_window=128000,
        name="OpenAI: GPT Audio Mini",
        owner="openai",
        description="A cost-efficient version of GPT Audio. The new snapshot features an upgraded decoder for more natural sounding voices and maintains better voice consistency. Input is priced at $0.60 per million...",
        canonical_slug="openai/gpt-audio-mini",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1768859419),
        pricing={'prompt': '0.0000006', 'completion': '0.0000024', 'audio': '0.0000006'},
        architecture={'modality': 'text+audio->text+audio', 'input_modalities': ['text', 'audio'], 'output_modalities': ['text', 'audio'], 'tokenizer': 'GPT', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 16384, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = GptAudioMiniModel.model
