"""Qwen3 8B model configuration for local deployment via Ollama.

This module defines the Qwen3 8B model from Alibaba Cloud, optimized for:
- Local, privacy-focused deployments
- Multilingual capabilities (especially Chinese/English)
- Code generation and reasoning tasks
- Resource-efficient inference
"""

from lib.abi.models.Model import ChatModel
from typing import Optional

ID = "qwen3:8b"
NAME = "Qwen3 8B"
DESCRIPTION = "Alibaba's Qwen3 8B model for local deployment. Excellent at code generation, reasoning, and multilingual tasks."
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
            temperature=0.3,  # Slightly creative for code/reasoning tasks
            # num_predict=4096,  # Max tokens to generate
        ),
        context_window=CONTEXT_WINDOW,
    )
    print("✅ Qwen3 8B model loaded successfully via Ollama")
    
except ImportError:
    print("⚠️  langchain_ollama not installed. Qwen3 8B model will not be available.")
    print("   Install with: pip install langchain-ollama")
except Exception as e:
    print(f"⚠️  Error loading Qwen3 8B model: {e}")
    print("   Make sure Ollama is running and 'qwen3:8b' model is pulled.")