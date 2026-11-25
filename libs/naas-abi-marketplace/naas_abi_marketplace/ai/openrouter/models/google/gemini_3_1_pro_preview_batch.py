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


class Gemini31ProPreviewBatchModel(ModelDefinition):
    CANONICAL_ID = "gemini-3.1-pro-preview:batch"
    MODEL_ID = "google/gemini-3.1-pro-preview:batch"
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
        context_window=1048576,
        name="Google: Gemini 3.1 Pro Preview (batch)",
        owner="google",
        description="Gemini 3.1 Pro Preview is Google’s frontier reasoning model, delivering enhanced software engineering performance, improved agentic reliability, and more efficient token usage across complex workflows. Building on the multimodal foundation...",
        canonical_slug="google/gemini-3.1-pro-preview-20260219",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1771509627),
        pricing={'prompt': '0.000001', 'completion': '0.000006', 'image': '0.000001', 'audio': '0.000001', 'web_search': '0.014', 'internal_reasoning': '0.000006', 'overrides': [{'min_prompt_tokens': 200000, 'prompt': '0.000002', 'completion': '0.000009', 'audio': '0.000002'}]},
        architecture={'modality': 'text+image+file+audio+video->text', 'input_modalities': ['audio', 'file', 'image', 'text', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Gemini', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'max_tokens', 'reasoning', 'reasoning_effort', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = Gemini31ProPreviewBatchModel.model
