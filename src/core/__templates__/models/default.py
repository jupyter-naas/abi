from src import secret
from lib.abi.models.Model import ChatModel

model: ChatModel
airgap_model: ChatModel
cloud_model: ChatModel
ai_mode = secret.get("AI_MODE")

if ai_mode == "airgap":
    from src.core.abi.models.airgap_qwen import model as airgap_model
    model = airgap_model
else:
    from src.core.chatgpt.models.gpt_4_1_mini import model as cloud_model
    model = cloud_model