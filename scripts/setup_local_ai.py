#!/usr/bin/env python3
"""Setup script for local AI models using Ollama."""

import subprocess
import time
import requests
import sys
from pathlib import Path

def run_command(cmd, check=True):
    """Run a shell command."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    return True

def wait_for_ollama():
    """Wait for Ollama to be ready."""
    print("Waiting for Ollama to start...")
    for i in range(30):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                print("✅ Ollama is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
        print(f"Waiting... ({i+1}/30)")
    
    print("❌ Ollama failed to start")
    return False

def pull_model(model_name):
    """Pull an Ollama model."""
    print(f"Pulling {model_name}...")
    cmd = ["docker", "exec", "abi-ollama-1", "ollama", "pull", model_name]
    return run_command(cmd)

def main():
    """Main setup function."""
    print("🚀 Setting up local AI models...")
    
    # Start services
    print("Starting Docker services...")
    if not run_command(["make", "local-up"]):
        print("❌ Failed to start services")
        return 1
    
    # Wait for Ollama
    if not wait_for_ollama():
        return 1
    
    # Pull required models
    models = [
        "gemma2:2b",           # Chat model (small, fast)
        "nomic-embed-text",    # Embedding model
        "gemma:2b"             # Alternative chat model
    ]
    
    for model in models:
        if not pull_model(model):
            print(f"❌ Failed to pull {model}")
            return 1
        print(f"✅ {model} ready!")
    
    print("\n🎉 Local AI setup complete!")
    print("💬 You can now use AI_MODE=local with:")
    print("   make chat-abi-agent")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
