from src import secret
from lib.abi.models.Model import ChatModel
import os

model: ChatModel
airgap_model: ChatModel
cloud_model: ChatModel
ai_mode = secret.get("AI_MODE")

if ai_mode == "airgap" or not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
    from src.core.abi.models.airgap_qwen import model as airgap_model
    model = airgap_model
else:
    from src.core.chatgpt.models.gpt_4_1_mini import model as cloud_model
    model = cloud_model