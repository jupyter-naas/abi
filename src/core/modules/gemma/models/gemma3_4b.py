"""Gemma3 4B model configuration for local deployment via Ollama.

This module defines Google's Gemma3 4B model, optimized for:
- Local, privacy-focused deployments  
- General-purpose conversational AI
- Lightweight resource usage
- Fast inference on consumer hardware
- Open-source alternative to cloud Gemini
"""

from lib.abi.models.Model import ChatModel
from typing import Optional

ID = "gemma3:4b"
NAME = "Gemma3 4B"
DESCRIPTION = "Google's open-source Gemma3 4B model for local deployment. Fast, lightweight alternative to cloud Gemini."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png"
CONTEXT_WINDOW = 8192
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
            temperature=0.4,  # Balanced creativity for general conversation
            # num_predict=2048,  # Reasonable output length for 4B model
        ),
        context_window=CONTEXT_WINDOW,
    )
    print("✅ Gemma3 4B model loaded successfully via Ollama")
    
except ImportError:
    print("⚠️  langchain_ollama not installed. Gemma3 4B model will not be available.")
    print("   Install with: pip install langchain-ollama")
except Exception as e:
    print(f"⚠️  Error loading Gemma3 4B model: {e}")
    print("   Make sure Ollama is running and 'gemma3:4b' model is pulled.")