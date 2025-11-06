from src import secret
from lib.abi.models.Model import ChatModel
from src.core.abi.models.airgap_qwen import model as airgap_model
from src.core.chatgpt.models.gpt_4_1_mini import model as cloud_model

model: ChatModel
ai_mode = secret.get("AI_MODE")
airgap_model: ChatModel = airgap_model
cloud_model: ChatModel = cloud_model

if ai_mode == "airgap":
    model = airgap_model
else:
    model = cloud_model