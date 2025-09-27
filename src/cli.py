from dotenv import load_dotenv
load_dotenv()
from dotenv import dotenv_values

from rich.console import Console
from rich.prompt import Prompt
import requests
import time
import os
import shutil
import yaml
import signal

ENV = "dev"

if not os.path.exists(".env"):
    with open(".env", "w") as f:
        f.write(f"ENV={ENV}\n")
        f.write("LOG_LEVEL=DEBUG\n")
    print("Created .env file with default values")

console = Console(style="")

dv = dotenv_values()

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
        console.print("⚠️  Local services not running. Attempting to start...", style="yellow")
        try:
            # Try to start services with automatic cleanup on failure
            result = subprocess.run(
                ["make", "local-down"],
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout
            )
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
    
    naas_key = Prompt.ask("What's your Naas API key?\nGet one for free at https://naas.ai/account/api-key", default="")
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

def define_config_file():
    import re
    
    if not os.path.exists(f"config.yaml"):
        shutil.copy("config.yaml.example", "config.yaml")
        console.print("\nCreated config.yaml file from config.yaml.example", style="blue")
        console.print("\nLet's configure your project settings:", style="blue")
        
        max_attempts = 3
        for attempt in range(max_attempts):
            workspace_id = Prompt.ask("What's your Naas workspace ID? (Find it at https://naas.ai/account/settings)")
            while not re.match(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", workspace_id):
                console.print("Invalid workspace ID format. It should be a UUID like: 96ce7ee7-e5f5-4bca-acf9-9d5d41317f81", style="red")
                workspace_id = Prompt.ask("Please enter a valid workspace ID")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.getenv('NAAS_API_KEY')}",
            }
            url = f"https://api.naas.ai/workspace/{workspace_id}"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                console.print("✅ Valid workspace ID.", style="green")
                break
            else:
                console.print("Invalid workspace ID. Please try again ({} attempts left).".format(max_attempts - attempt), style="red")
                
        github_repo = Prompt.ask("What's your Github repository name? (e.g. jupyter-naas/abi)")
        github_repo = github_repo.replace("https://github.com/", "")
        if github_repo.endswith("/"):
            github_repo = github_repo[:-1]
        while not (github_repo == "jupyter-naas/abi" or re.match(r"^[a-zA-Z0-9-]+/[a-zA-Z0-9-]+$", github_repo)):
            console.print("Invalid repository format. It should be 'jupyter-naas/abi' or follow the format 'owner/repo'", style="red")
            github_repo = Prompt.ask("Please enter a valid repository name")
        
        # Read and modify the config file
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
            
        config["config"]["workspace_id"] = workspace_id
        config["config"]["github_repository"] = github_repo
        
        # Derive other settings from repo name
        repo_name = github_repo.split("/")[-1]  # Get last part after /
        clean_name = repo_name.replace(".", "")  # Remove dots
        
        config["config"]["storage_name"] = clean_name
        config["config"]["space_name"] = clean_name
        config["config"]["api_title"] = f"{clean_name.upper()} API"
        config["config"]["api_description"] = f"API for {clean_name.upper()} AI system."
        
        # Write back the updated config
        with open("config.yaml", "w") as f:
            yaml.dump(config, f)
            
        print("\nConfiguration saved to config.yaml")
        
    if not os.path.exists(f"config.{ENV}.yaml") and os.path.exists("config.yaml"):
        shutil.copy("config.yaml", f"config.{ENV}.yaml")
        print("Created config.env.yaml file from config.yaml")

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

def extract_required_keys_from_module(module_path):
    """Extract all secret.get() keys from a module's requirements function."""
    import re
    import os
    
    # Read the module file
    file_path = module_path.replace(".", "/") + "/__init__.py"
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find the requirements function
        req_match = re.search(r'def requirements\(\):(.*?)(?=def|\Z)', content, re.DOTALL)
        if not req_match:
            return []
        
        requirements_code = req_match.group(1)
        
        # Extract all secret.get() calls
        pattern = r"secret\.get\(['\"]([^'\"]*)['\"]"
        keys = re.findall(pattern, requirements_code)
        
        return list(set(keys))  # Remove duplicates
    except Exception as e:
        # console.print(f"⚠️ Could not extract keys from {module_path}: {e}", style="yellow")
        return []

def check_modules_requirements():
    import yaml
    import importlib
    # Find all module paths by checking for specific folders
    all_modules: list[str] = []
    base_paths: list[str] = ["src/core", "src/custom", "src/marketplace"]
    module_indicators: list[str] = ["apps", "integrations", "agents", "ontologies", "pipelines", "workflows"]
    
    for base_path in base_paths:
        if not os.path.exists(base_path):
            continue

        # Walk through directory tree
        for root, dirs, files in os.walk(base_path):
            # Skip __template__ directory
            if "__templates__" in root:
                continue
                
            # Check if any module indicator folders exist in current directory
            # and __init__.py exists
            if any(indicator in dirs for indicator in module_indicators) and "__init__.py" in files:
                all_modules.append(root)
    # console.print(f"Found {len(all_modules)} modules available in the project.", style="blue")

    # Get module enabled from config
    with open(f"config.{ENV}.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    config_modules: list = [m["path"] for m in config["modules"]]
    enabled_modules: list = [m["path"] for m in config["modules"] if m["enabled"]]
    console.print(f"Found {len(enabled_modules)} modules enabled in the project.\n", style="blue")
    
    # Keep track of modules to disable
    modules_to_enable: list = []
    modules_to_disable: list = []
    
    for module_path in sorted(all_modules):
        try:
            if module_path not in config_modules:
                module_to_add = Prompt.ask(f"Module '{module_path}' is available in the project but not enabled in your config file. Do you want to enable it? (Press Enter to skip)", choices=["y", "n"], default="n")
                if module_to_add != "y":
                    modules_to_disable.append(module_path)
                    continue
                modules_to_enable.append(module_path)
                enabled_modules.append(module_path)

            if module_path not in enabled_modules:
                continue
            
            # Import the module's requirements function
            module_name = module_path.replace("/", ".")
            module = importlib.import_module(f"{module_name}")
            # Get the module name for display
            module_display_name = module_path.split("/")[-1]
            
            if hasattr(module, "requirements"):
                # Extract all required keys from the module
                required_keys = extract_required_keys_from_module(module_name)
                
                if not required_keys:
                    console.print(f"✅ '{module_display_name}' module requirements satisfied (no secret keys required)", style="green")
                    continue
                
                console.print(f"🔑 '{module_display_name}' module requires the following keys: {', '.join(required_keys)}", style="cyan")
                
                # Ask user for each missing key
                all_keys_provided = True
                for key in required_keys:
                    current_value = dv.get(key)
                    if not current_value:
                        user_input = Prompt.ask(
                            f"What is your {key}? (press enter to skip)",
                            default=""
                        )
                        
                        if user_input.strip():
                            append_to_dotenv(key, user_input.strip())
                            console.print(f"✅ {key} added", style="green")
                        else:
                            console.print(f"⏭️  {key} skipped", style="yellow")
                            all_keys_provided = False
                            # If module not previously enabled, don't add it to modules_to_enable
                            if module_path in modules_to_enable:
                                modules_to_enable.remove(module_path)
                            if module_path in modules_to_disable:
                                modules_to_disable.append(module_path)
                            break  # Exit loop early since module will be disabled
                
                # If any key was skipped, disable the module
                if not all_keys_provided:
                    modules_to_disable.append(module_path)
                    console.print(f"❌ '{module_display_name}' module will be disabled due to missing required keys", style="red")
                else:
                    console.print(f"✅ '{module_display_name}' module requirements satisfied", style="green")
            else:
                console.print(f"✅ '{module_display_name}' module requirements satisfied.", style="green")
        except ImportError:
            console.print(f"⚠️ Could not check requirements for {module_path}", style="yellow")
            continue
    
    # Update config file with enabled/disabled modules
    config_file = f"config.{ENV}.yaml"
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
        
    # Sort modules to maintain consistent order
    config["modules"] = sorted(config["modules"], key=lambda x: x["path"])
        
    # Add new modules to enable
    if len(modules_to_enable) > 0:
        console.print(f"\nEnabling {len(modules_to_enable)} modules...\n", style="green")
    for module_path in modules_to_enable:
        if not any(m["path"] == module_path for m in config["modules"]):
            config["modules"].append({
                "path": module_path,
                "enabled": True
            })
            console.print(f"   • {module_path} enabled", style="green")
    
    # Disable modules with missing requirements
    if len(modules_to_disable) > 0:
        console.print(f"\nDisabling {len(modules_to_disable)} modules...\n", style="red")
    for module_path in modules_to_disable:
        module_exists = False
        for module in config["modules"]:
            if module["path"] == module_path:
                module["enabled"] = False
                console.print(f"   • {module_path} disabled", style="red")
                module_exists = True
                break
        if not module_exists:
            config["modules"].append({
                "path": module_path,
                "enabled": False
            })
            console.print(f"   • {module_path} added and disabled", style="red")
            
    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    time.sleep(5)
    
    if modules_to_disable:
        console.print(f"\n✅ Configuration updated in {config_file} - {len(modules_to_disable)} modules disabled\n", style="yellow")
    elif modules_to_enable:
        console.print(f"\n✅ Configuration updated in {config_file} - {len(modules_to_enable)} modules enabled\n", style="green")
    else:
        console.print("\n🎉 All enabled modules have their requirements satisfied!\n", style="green")

checks = [
    define_ai_mode,
    define_naas_api_key,
    define_config_file,
    define_abi_api_key,
    define_oxigraph_url,
    define_postgres_url,
    check_modules_requirements,
]
    
def main(agent_name="AbiAgent"):
    # Load environment first to check AI_MODE
    for key, value in dotenv_values().items():
        os.environ[key] = value
    
    ai_mode = os.getenv("AI_MODE")
    
    
    # Skip cloud service checks in airgap mode for instant startup
    if ai_mode == "airgap":
        # Only run essential checks for airgap mode
        essential_checks = [
            personnal_information,
            define_ai_mode,
            define_config_file,
            define_abi_api_key,
            define_oxigraph_url,
            define_postgres_url,
        ]
        for f in essential_checks:
            f()
    else:
        # Run all checks for cloud/local modes
        for f in checks:
            f()

    # Reload src/__init__.py to ensure latest changes
    import importlib
    import src
    importlib.reload(src)
    
    # Ensure all local services are running (Oxigraph, PostgreSQL, etc.)
    ensure_local_services_running()
    
    if ai_mode != "airgap":
        console.print(f"Starting agent...", style="green")
    from src.core.abi.apps.terminal_agent.main import generic_run_agent
    generic_run_agent(agent_name)

if __name__ == "__main__":
    import sys
    
    # Parse command line arguments for agent name
    agent_name = "AbiAgent"  # default
    if len(sys.argv) > 1:
        agent_name = sys.argv[1]
    
    main(agent_name=agent_name)
