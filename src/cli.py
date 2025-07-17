# Suppress debug logs for cleaner conversational experience
import os
os.environ["LOG_LEVEL"] = "CRITICAL"  # Even more aggressive

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

console = Console(style="")

# Catch ctrl+c
import signal

def signal_handler(sig, frame):
    console.print("\n\n🛑 Ctrl+C pressed. See you next time! 👋", style="bright_red")
    exit(0)

signal.signal(signal.SIGINT, signal_handler)

def loading_animation(message, duration=2):
    """Show a loading animation"""
    with console.status(message, spinner="dots"):
        time.sleep(duration)

def celebration_message():
    """Show celebration message"""
    messages = [
        "🎉 Fantastic! You're all set!",
        "🚀 Ready for takeoff!",
        "✨ Magic happens here!",
        "🎯 Bulls-eye! Configuration complete!",
        "🏆 You're a configuration champion!"
    ]
    
    chosen_message = random.choice(messages)
    console.print(f"\n{chosen_message}", style="bright_green bold")

def define_ai_mode():
    dv = dotenv_values()
    
    if "AI_MODE" in dv:
        return

    console.print("\n👋 Hi there! I'm ABI, your AI assistant.", style="bright_blue bold")
    console.print("I need to set myself up first. This will just take a moment...", style="bright_cyan")
    
    console.print("\nI can run in two ways:", style="bright_cyan")
    console.print("   🌐 Using cloud models (more powerful, but needs internet)")
    console.print("   🏠 Running locally on your machine (private and works offline)")
    
    prompt = Prompt.ask(
        "\nWhich would you prefer?", 
        choices=["Cloud", "Local"], 
        default="Cloud", 
        case_sensitive=False
    )
    
    prompt = prompt.lower()
    
    if prompt == "cloud":
        dv["AI_MODE"] = "cloud"
        console.print("Great choice! I'll use cloud models for maximum power. ☁️", style="bright_cyan")
    else:
        dv["AI_MODE"] = "local"
        console.print("Perfect! I'll run locally to keep everything private. 🔒", style="bright_cyan")
        
    if prompt == "cloud" and dv.get("OPENAI_API_KEY") is None:
        console.print("\nI'll need an OpenAI API key to access those cloud models.", style="bright_yellow")
        console.print("💡 You can get one at https://platform.openai.com/api-keys", style="dim")
        
        openai_api_key = ""
        attempts = 0
        
        while openai_api_key == "":
            if attempts > 0:
                console.print("Hmm, that doesn't look right. Could you try again?", style="bright_red")
            
            openai_api_key = Prompt.ask("Please paste your OpenAI API key")
            
            if not openai_api_key.startswith("sk-"):
                console.print("That doesn't look like a valid OpenAI key (they start with 'sk-')", style="bright_red")
                openai_api_key = ""
                attempts += 1
                
                if attempts >= 3:
                    console.print("💡 Need help? Check out: https://help.openai.com/en/articles/4936850", style="bright_blue")
            
        loading_animation("🔐 Securing your API key...")
        with open(".env", "a") as f:
            f.write(f"\nOPENAI_API_KEY={openai_api_key}\n")
        console.print("Perfect! I've saved that securely. ✅", style="bright_green")
    
    with open(".env", "a") as f:
        f.write(f"\nAI_MODE={dv['AI_MODE']}\n")
    
    loading_animation("Setting up my brain...")
    console.print("All set! I'm ready to think. ✅", style="bright_green")

def define_naas_api_key():
    dv = dotenv_values()
    
    if "NAAS_API_KEY" in dv:
        return
    
    console.print("\nNow I'd like to connect to NAAS - it's a data platform that helps me work with your information.", style="bright_magenta bold")
    console.print("This will let me help you with data workflows and automation.", style="bright_cyan")
    
    naas_api_key = ""
    attempts = 0

    while naas_api_key == "":
        if attempts == 0:
            console.print("\nYou can get your NAAS API key here: https://naas.ai/account/api-key", style="bright_blue")
            console.print("💡 Just copy it from your account page and paste it here.", style="dim")
        
        naas_api_key = Prompt.ask("Please paste your NAAS API key")
        
        loading_animation("Let me check that key...")
        
        try:
            r = requests.get("https://api.naas.ai/iam/apikey", headers={"Authorization": f"Bearer {naas_api_key}"})

            if r.status_code != 200:
                console.print("That key doesn't seem to work. Could you try again?", style="bright_red")
                naas_api_key = ""
                attempts += 1
                
                if attempts >= 3:
                    console.print("💡 Still having trouble? You can contact support: https://naas.ai/support", style="bright_blue")
            else:
                console.print("Excellent! That key works perfectly. ✅", style="bright_green")
                
        except requests.RequestException:
            console.print("I'm having trouble connecting right now. Please check your internet and try again.", style="bright_yellow")
            naas_api_key = ""
            attempts += 1

    loading_animation("Saving your NAAS connection...")
    with open(".env", "a") as f:
        f.write(f"\nNAAS_API_KEY={naas_api_key}\n")
    
    console.print("Perfect! I'm now connected to NAAS. ✅", style="bright_green")

def define_abi_api_key():
    dv = dotenv_values()
    
    if "ABI_API_KEY" in dv:
        return
    
    console.print("\n" + "="*50, style="bright_green")
    console.print("🎲 ABI API KEY GENERATION!", style="bright_green bold")
    console.print("="*50, style="bright_green")
    
    import uuid
    
    console.print("\n🎰 Generating a unique ABI API key for you...", style="bright_cyan")
    loading_animation("🎲 Rolling the dice...")
    
    abi_api_key = str(uuid.uuid4())
    
    console.print(f"✨ Your unique ABI API key: {abi_api_key[:8]}...", style="bright_yellow")
    
    with open(".env", "a") as f:
        f.write(f"\nABI_API_KEY={abi_api_key}\n")
    
    console.print("✅ ABI API key generated and saved!", style="bright_green")

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


checks = [
    define_abi_api_key,
    define_ai_mode,
    define_naas_api_key,
    ensure_ollama_running
]

def welcome_message():
    """Simple, natural greeting"""
    console.print("\n👋 Hi! I'm ABI, your AI assistant.", style="bold bright_blue")
    console.print("Let me get ready for you...", style="dim")

def completion_message():
    """Show completion message with summary"""
    console.print("\nPerfect! I'm all set up and ready to help you. ✨", style="bright_green bold")
    
    celebration_message()
    
    # Show what's configured in a friendly way
    dv = dotenv_values()
    ai_mode = dv.get('AI_MODE', 'Unknown').title()
    
    console.print(f"\n💡 I'm running in {ai_mode} mode and connected to NAAS.", style="bright_cyan")
    console.print("Now we can start chatting! Just tell me what you'd like to do.", style="bright_white")

def agent_selection():
    # Suppress all logging right before agent startup
    import logging
    logging.getLogger().setLevel(logging.CRITICAL)
    
    # Also suppress loguru logger
    try:
        from loguru import logger
        logger.remove()
        logger.add(lambda x: None)  # No-op handler
    except:
        pass
    
    console.print("Ready! What can I help you with?", style="bright_green")
    from src.core.apps.terminal_agent.main import generic_run_agent
    generic_run_agent("SupervisorAgent")
    

def main():
    from rich.console import Console
    from rich.prompt import Prompt
    import time
    import threading
    import os
    
    console = Console()
    
    # Check if this is first boot
    dv = dotenv_values()
    is_first_boot = "AI_MODE" not in dv
    
    if is_first_boot:
        # Natural setup experience
        print("\nHello! I'm ABI, your AI assistant.")
        print("Since this is our first time meeting, I'd like to ask you a few quick questions.")
        print("This will help me understand how to work best with you.\n")
        
        # Collect basic user info
        first_name = Prompt.ask("What's your first name?")
        last_name = Prompt.ask("And your last name?")
        email = Prompt.ask("What's your email address?", default="")
        
        print(f"\nNice to meet you, {first_name}.")
        
        # Simple AI mode choice
        print("I can run in two ways:")
        print("  1. Locally for privacy")
        print("  2. In the cloud for more power")
        mode_choice = Prompt.ask("Which would you prefer?", choices=["1", "2"], default="1")
        ai_mode = "local" if mode_choice == "1" else "cloud"
        
        # Optional Naas key
        print(f"\nOne last thing - do you have a Naas API key for enhanced features?")
        print("You can get one for free by signing up at naas.ai and visiting naas.ai/account/api-key")
        naas_key = Prompt.ask("(Paste it here, or press Enter to skip)", default="")
        
        # Save configuration
        import secrets
        api_key = secrets.token_urlsafe(32)
        
        with open(".env", "w") as f:
            f.write(f"AI_MODE={ai_mode}\n")
            f.write(f"ABI_API_KEY={api_key}\n")
            f.write(f"USER_FIRST_NAME={first_name}\n")
            f.write(f"USER_LAST_NAME={last_name}\n")
            f.write(f"USER_EMAIL={email}\n")
            if naas_key:
                f.write(f"NAAS_API_KEY={naas_key}\n")
        
        print(f"\nThank you, {first_name}. Please wait as your individualized AI assistant is initiated...\n")
    
    # Load environment variables and force dev mode
    from dotenv import load_dotenv
    load_dotenv()
    import os
    os.environ['ENV'] = 'dev'  # Force development mode to avoid network calls
    
    # Matrix-style startup animation
    loading = True
    
    def startup_loader():
        i = 0
        while loading:
            dots_count = i % 4  # 0, 1, 2, 3, then repeat
            if dots_count == 0:
                dots = "   "  # No dots, just spaces
            else:
                dots = "." * dots_count + " " * (3 - dots_count)  # Pad to 3 char width
            print(f"\r\033[92mLoading{dots}\033[0m", end="", flush=True)
            time.sleep(0.5)
            i += 1
    
    # Start the animation
    loader_thread = threading.Thread(target=startup_loader)
    loader_thread.start()
    
    # Suppress all logging during module loading
    import logging
    logging.getLogger().setLevel(logging.CRITICAL)
    try:
        from loguru import logger
        logger.remove()
        logger.add(lambda x: None)
    except:
        pass
    
    # Brief pause for module loading
    time.sleep(0.5)
    
    # Stop the animation
    loading = False
    loader_thread.join()
    
    # Clear the loading line
    print("\r" + " " * 20 + "\r", end="", flush=True)
    
    # Simple, conversational greeting for returning users
    first_name = os.getenv("USER_FIRST_NAME", "there")
    print(f"Hi {first_name}!\n")

    from src.core.apps.terminal_agent.main import generic_run_agent
    generic_run_agent("SupervisorAgent")

if __name__ == "__main__":
    main()
