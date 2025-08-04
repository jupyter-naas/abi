"""DeepSeek R1 8B model configuration for local deployment via Ollama.

This module defines the DeepSeek R1 8B model, specifically optimized for:
- Advanced reasoning and problem-solving
- Mathematical computations and proofs
- Complex logical analysis
- Scientific research assistance
- Chain-of-thought reasoning
"""

from lib.abi.models.Model import ChatModel
from typing import Optional

ID = "deepseek-r1:8b"
NAME = "DeepSeek R1 8B"
DESCRIPTION = "DeepSeek's R1 8B reasoning model for advanced problem-solving, mathematics, and logical analysis."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 32768
OWNER = "ollama"

model: Optional[ChatModel] = None

try:
    from langchain_ollama import ChatOllama
    
    model = ChatModel(
        model_id=ID,
        name=NAME,
        description=DESCRIPTION,
        image=IMAGE,
        owner=OWNER,
        model=ChatOllama(
            model=ID,
            temperature=0.1,  # Low temperature for precise reasoning
            # num_predict=4096,  # Max tokens for detailed explanations
        ),
        context_window=CONTEXT_WINDOW,
    )
    print("✅ DeepSeek R1 8B model loaded successfully via Ollama")
    
except ImportError:
    print("⚠️  langchain_ollama not installed. DeepSeek R1 8B model will not be available.")
    print("   Install with: pip install langchain-ollama")
except Exception as e:
    print(f"⚠️  Error loading DeepSeek R1 8B model: {e}")
    print("   Make sure Ollama is running and 'deepseek-r1:8b' model is pulled.")