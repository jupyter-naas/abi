from internal.gaia import ABIModule
from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from pydantic import SecretStr


class Qwen36Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.QWEN_3_6
    MODEL_ID = "Qwen/Qwen3.6-35B-A3B-FP8"
    PROVIDER = ModelProvider.QWEN

    _cfg = ABIModule.get_instance().configuration

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        name="Qwen 3.6 35B A3B FP8 (LiteLLM)",
        description="Qwen 3.6 served by Zettafox's LiteLLM OpenAI-compatible endpoint.",
        context_window=500000,
        model=ChatOpenAI(
            model=MODEL_ID,
            api_key=SecretStr("unused"),
            base_url="https://llm.zettafox.com/litellm",
            default_headers={"Authorization": _cfg.qwen_litellm_auth_header},
            temperature=0,
            top_p=0.1,
            timeout=120,
            max_retries=3,
            model_kwargs={"max_tokens": 100000},
            extra_body={"repetition_penalty": 1.1},
        ),
    )


# Back-compat for direct importers — ``from ... import model``.
model: ChatModel = Qwen36Model.model
