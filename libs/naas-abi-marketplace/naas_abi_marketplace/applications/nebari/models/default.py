from naas_abi import secret
from naas_abi_core.models.Model import ChatModel

model: ChatModel
airgap_model: ChatModel
cloud_model: ChatModel
ai_mode = secret.get("AI_MODE")

if ai_mode == "airgap":
    from naas_abi.models.airgap_qwen import model as airgap_model

    model = airgap_model
else:
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model as cloud_model

    model = cloud_model
