# # Suppress debug logs for cleaner conversational experience
# import os
# os.environ["LOG_LEVEL"] = "CRITICAL"  # Even more aggressive

from dotenv import load_dotenv
load_dotenv()
from dotenv import dotenv_values

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.table import Table
from rich.markdown import Markdown
import rich
import requests
import time
import random
import os

console = Console(style="")

dv = dotenv_values()

# Catch ctrl+c
import signal

def signal_handler(sig, frame):
    console.print("\n\n🛑 Ctrl+C pressed. See you next time! 👋", style="bright_red")
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)

def append_to_dotenv(key, value):
    with open(".env", "a") as f:
        f.write(f"{key}={value}\n")

def ensure_ollama_running():
    dv = dotenv_values()
    if dv["AI_MODE"] != "local":
        return
    
    # Detect os because on WSL the port will be different, we need to find the ip address of the machine.
    if os.name == "nt":
        ip_address = "172.17.0.1"
    else:
        ip_address = "localhost"
        
    ollama_running = False
    
    
    while not ollama_running:
        try:
            r = requests.get(f"http://{ip_address}:11434/api/version")
            
            if r.status_code == 200:
                #console.print("🟢 Ollama is running!", style="bright_green")
                ollama_running = True
                break
        except Exception as e:
            console.print("I need Ollama running to use my local brain. Let me help you get it started!", style="bright_cyan")
            console.print("💡 Just run: `ollama run qwen3:8b`", style="dim")
            console.print("💡 If you don't have Ollama yet, get it here: https://ollama.com/download", style="dim")
        
        time.sleep(5)
    
    # Pulling qwen3:8b
    console.print("Setting up my brain... this might take a moment.", style="dim")
    # Equivalent to: curl "http://localhost:11434/api/pull" -d '{"model": "qwen3:8b"}'
    with requests.post(
        "http://localhost:11434/api/pull",
        data='{"model": "qwen3:8b"}',
        headers={"Content-Type": "application/json"},
        stream=True
    ) as response:
        response.raise_for_status()
        # Just wait silently without showing technical progress
        for line in response.iter_lines(decode_unicode=True):
            if line:
                import json
                data = json.loads(line)
                # Don't show progress bar - just let it happen quietly


def personnal_information():
    if "FIRST_NAME" in dv:
        return
    
    # Natural setup experience
    print("\nHello! I'm ABI, your AI assistant.")
    print("Since this is our first time meeting, I'd like to ask you a few quick questions.")
    print("This will help me understand how to work best with you.\n")
    
    # Collect basic user info
    first_name = Prompt.ask("What's your first name?")
    last_name = Prompt.ask("And your last name?")
    email = Prompt.ask("What's your email address?", default="")
    
    print(f"\nNice to meet you, {first_name}.")
    
    append_to_dotenv("FIRST_NAME", first_name)
    append_to_dotenv("LAST_NAME", last_name)
    append_to_dotenv("EMAIL", email)


def define_ai_mode():
    if "AI_MODE" in dv:
        return
    
    # Simple AI mode choice
    print("I can run in two ways:")
    print("  1. Locally for privacy")
    print("  2. In the cloud for more power")
    mode_choice = Prompt.ask("Which would you prefer?", choices=["1", "2"], default="1")
    ai_mode = "local" if mode_choice == "1" else "cloud"
    
    append_to_dotenv("AI_MODE", ai_mode)

def define_naas_api_key():
    if "NAAS_API_KEY" in dv:
        return

    # Optional Naas key
    print(f"\nOne last thing - do you have a Naas API key for enhanced features?")
    print("You can get one for free by signing up at naas.ai and visiting naas.ai/account/api-key")
    naas_key = Prompt.ask("(Paste it here, or press Enter to skip)", default="")
    
    valid_naas_api_key = False
    while not valid_naas_api_key:
        try:
            r = requests.get("https://api.naas.ai/iam/apikey", headers={"Authorization": f"Bearer {naas_key}"})
            r.raise_for_status()
            if r.status_code == 200:
                valid_naas_api_key = True
        except Exception as e:
            print("Invalid Naas API key. Please try again.")
            naas_key = Prompt.ask("(Paste it here, or press Enter to skip)", default="")
    
    append_to_dotenv("NAAS_API_KEY", naas_key)
    

def define_abi_api_key():
    if "ABI_API_KEY" in dv:
        return
    
    import secrets
    api_key = secrets.token_urlsafe(32)
    
    append_to_dotenv("ABI_API_KEY", api_key)

def define_cloud_api_keys():
    if "AI_MODE" not in dv or dv["AI_MODE"] == "local":
        return
    
    # Openai
    if "OPENAI_API_KEY" not in dv:
        openai_key = Prompt.ask("What is your OpenAI API key? (press enter to skip)", default="")
        append_to_dotenv("OPENAI_API_KEY", openai_key)
    
    # Anthropic
    if "ANTHROPIC_API_KEY" not in dv:
        anthropic_key = Prompt.ask("What is your Anthropic API key? (press enter to skip)", default="")
        append_to_dotenv("ANTHROPIC_API_KEY", anthropic_key)
        
    if "GOOGLE_API_KEY" not in dv:
        google_key = Prompt.ask("What is your Google API key? (press enter to skip)", default="")
        append_to_dotenv("GOOGLE_API_KEY", google_key)
    

checks = [
    personnal_information,
    define_ai_mode,
    define_naas_api_key,
    define_abi_api_key,
    define_cloud_api_keys,
]
    

def main():
    for f in checks:
        f()
    
    
    for key, value in dotenv_values().items():
        os.environ[key] = value
    
    os.environ['ENV'] = 'dev'  # Force development mode to avoid network calls
    
    from src.core.apps.terminal_agent.main import generic_run_agent
    generic_run_agent("SupervisorAgent")

if __name__ == "__main__":
    main()
