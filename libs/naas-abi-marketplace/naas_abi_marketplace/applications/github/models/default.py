from typing import Literal

from naas_abi_core.models.Model import ChatModel
from naas_abi_marketplace.applications.github import ABIModule


def get_model() -> ChatModel:
    ai_mode: Literal["cloud", "local", "airgap"] = (
        ABIModule.get_instance().configuration.global_config.ai_mode
    )
    if (
        ai_mode == "airgap"
        or not ABIModule.get_instance().configuration.openai_api_key
        and not ABIModule.get_instance().configuration.openrouter_api_key
    ):
        from naas_abi_marketplace.ai.qwen.models.qwen3_8b import model as airgap_model

        return airgap_model
    else:
        from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import (
            model as cloud_model,
        )

        return cloud_model
