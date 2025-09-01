# # Suppress debug logs for cleaner conversational experience
# import os
# os.environ["LOG_LEVEL"] = "CRITICAL"  # Even more aggressive

from dotenv import load_dotenv
load_dotenv()
from dotenv import dotenv_values

from rich.console import Console
from rich.prompt import Prompt
import requests
import time
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
        f.write(f"\n{key}={value}\n")

def ensure_local_services_running():
    """Ensure all local services (Oxigraph, PostgreSQL, etc.) are running."""
    import subprocess
    
    oxigraph_url = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
    
    # Check if Oxigraph is accessible (indicates local services are running)
    services_running = False
    try:
        r = requests.get(f"{oxigraph_url}/query", params={"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"}, timeout=2)
        if r.status_code == 200:
            services_running = True
    except:
        pass
    
    if not services_running:
        console.print("⚠️ Local services not running. Attempting to start...", style="yellow")
        try:
            # Try to start services with automatic cleanup on failure
            result = subprocess.run(
                ["make", "local-up"],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode != 0:
                console.print("❌ Failed to start services automatically.", style="red")
                console.print("🔧 Try running: make docker-cleanup && make local-up", style="cyan")
                console.print("💡 Or start services manually and restart this command.", style="dim")
                return
        except subprocess.TimeoutExpired:
            console.print("⏱️ Service startup timed out. Docker may be stuck.", style="yellow")
            console.print("🔧 Try: make docker-cleanup && make local-up", style="cyan")
            return
        except subprocess.CalledProcessError:
            console.print("❌ Could not start local services.", style="yellow")
            console.print("🔧 Try: make docker-cleanup && make local-up", style="cyan")
            return
            
            # Wait for services to be ready
            max_attempts = 30  # PostgreSQL + Oxigraph may take longer
            for attempt in range(max_attempts):
                try:
                    r = requests.get(f"{oxigraph_url}/query", params={"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"}, timeout=2)
                    if r.status_code == 200:
                        console.print("✓ Local services are ready!", style="bright_green")
                        console.print("✓ Oxigraph (Knowledge Graph): http://localhost:7878", style="dim")
                        console.print("✓ PostgreSQL (Agent Memory): localhost:5432", style="dim")
                        console.print("✓ YasGUI (SPARQL Editor): http://localhost:3000", style="dim")
                        break
                except:
                    pass
                time.sleep(2)
                if attempt == max_attempts - 1:
                    console.print("⚠️ Local services are taking longer than expected to start", style="yellow")
        except subprocess.CalledProcessError:
            console.print("⚠️ Could not start local services. Make sure Docker is running.", style="yellow")
            console.print("You can start them manually with: make local-up", style="dim")

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
        except Exception:
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
                json.loads(line)
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
    print("\nOne last thing - do you have a Naas API key for enhanced features?")
    print("You can get one for free by signing up at naas.ai and visiting naas.ai/account/api-key")
    naas_key = Prompt.ask("(Paste it here, or press Enter to skip)", default="")
    
    valid_naas_api_key = False
    while not valid_naas_api_key:
        try:
            r = requests.get("https://api.naas.ai/iam/apikey", headers={"Authorization": f"Bearer {naas_key}"})
            r.raise_for_status()
            if r.status_code == 200:
                valid_naas_api_key = True
        except Exception:
            print("Invalid Naas API key. Please try again.")
            naas_key = Prompt.ask("(Paste it here, or press Enter to skip)", default="")
    
    append_to_dotenv("NAAS_API_KEY", naas_key)
    

def define_abi_api_key():
    if "ABI_API_KEY" in dv:
        return
    
    import secrets
    api_key = secrets.token_urlsafe(32)
    
    append_to_dotenv("ABI_API_KEY", api_key)

def define_oxigraph_url():
    if "OXIGRAPH_URL" in dv:
        return
    
    # Default to local Oxigraph in local mode
    oxigraph_url = "http://localhost:7878"
    append_to_dotenv("OXIGRAPH_URL", oxigraph_url)

def define_postgres_url():
    if "POSTGRES_URL" in dv:
        return
    
    # Default to local PostgreSQL for agent memory persistence
    # Use localhost since CLI runs outside containers
    postgres_url = "postgresql://abi_user:abi_password@localhost:5432/abi_memory"
    append_to_dotenv("POSTGRES_URL", postgres_url)

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
    define_oxigraph_url,
    define_postgres_url,
    define_cloud_api_keys,
]
    

def main():
    for f in checks:
        f()
    
    
    for key, value in dotenv_values().items():
        os.environ[key] = value
    
    os.environ['ENV'] = 'dev'  # Force local mode to avoid network calls
    
    # Ensure all local services are running (Oxigraph, PostgreSQL, etc.)
    ensure_local_services_running()
    
    from src.core.apps.terminal_agent.main import generic_run_agent
    generic_run_agent("AbiAgent")

if __name__ == "__main__":
    main()
