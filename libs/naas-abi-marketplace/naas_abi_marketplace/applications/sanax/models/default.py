from naas_abi_core.models.Model import ChatModel
from naas_abi_marketplace.applications.sanax import ABIModule

model: ChatModel
ai_mode = ABIModule.get_instance().configuration.global_config.ai_mode

if ai_mode == "airgap":
    from naas_abi_marketplace.ai.qwen.models.qwen3_8b import model as airgap_model

    model = airgap_model
else:
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model as cloud_model

    model = cloud_model
