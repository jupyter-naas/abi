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


class RelaceApply3Model(ModelDefinition):
    CANONICAL_ID = "relace-apply-3"
    MODEL_ID = "relace/relace-apply-3"
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
        context_window=256000,
        name="Relace: Relace Apply 3",
        owner="relace",
        description="Relace Apply 3 is a specialized code-patching LLM that merges AI-suggested edits straight into your source files. It can apply updates from GPT-4o, Claude, and others into your files at...",
        canonical_slug="relace/relace-apply-3",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1758891572),
        pricing={'prompt': '0.00000085', 'completion': '0.00000125'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 256000, 'max_completion_tokens': 128000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['max_tokens', 'seed', 'stop'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = RelaceApply3Model.model
