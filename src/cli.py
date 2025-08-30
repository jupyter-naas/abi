#!/usr/bin/env python3
"""
ABI Command Line Interface

Main CLI for ABI with subcommands for various operations including
AI Network management, agent interaction, and system administration.
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()
from dotenv import dotenv_values

from rich.console import Console
from rich.prompt import Prompt
import requests
import time

console = Console(style="")

# Catch ctrl+c
import signal

def signal_handler(sig, frame):
    console.print("\n\n🛑 Ctrl+C pressed. See you next time! 👋", style="bright_red")
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)

def append_to_dotenv(key, value):
    with open(".env", "a") as f:
        f.write(f"{key}={value}\n")

def ensure_dev_services_running():
    """Ensure all development services (Oxigraph, PostgreSQL, etc.) are running."""
    import subprocess
    
    oxigraph_url = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
    
    # Check if Oxigraph is accessible (indicates dev services are running)
    services_running = False
    try:
        r = requests.get(f"{oxigraph_url}/query", params={"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"}, timeout=2)
        if r.status_code == 200:
            services_running = True
    except:
        pass
    
    if not services_running:
        console.print("⚠️ Development services not running. Attempting to start...", style="yellow")
        try:
            # Try to start services with automatic cleanup on failure
            result = subprocess.run(
                ["make", "dev-up"],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode != 0:
                console.print("❌ Failed to start services automatically.", style="red")
                console.print("🔧 Try running: make docker-cleanup && make dev-up", style="cyan")
                console.print("💡 Or start services manually and restart this command.", style="dim")
                return
        except subprocess.TimeoutExpired:
            console.print("⏱️ Service startup timed out. Docker may be stuck.", style="yellow")
            console.print("🔧 Try: make docker-cleanup && make dev-up", style="cyan")
            return
        except subprocess.CalledProcessError:
            console.print("❌ Could not start development services.", style="yellow")
            console.print("🔧 Try: make docker-cleanup && make dev-up", style="cyan")
            return
            
            # Wait for services to be ready
            max_attempts = 30  # PostgreSQL + Oxigraph may take longer
            for attempt in range(max_attempts):
                try:
                    r = requests.get(f"{oxigraph_url}/query", params={"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"}, timeout=2)
                    if r.status_code == 200:
                        console.print("✓ Development services are ready!", style="bright_green")
                        console.print("✓ Oxigraph (Knowledge Graph): http://localhost:7878", style="dim")
                        console.print("✓ PostgreSQL (Agent Memory): localhost:5432", style="dim")
                        console.print("✓ YasGUI (SPARQL Editor): http://localhost:3000", style="dim")
                        break
                except:
                    pass
                time.sleep(2)
                if attempt == max_attempts - 1:
                    console.print("⚠️ Development services are taking longer than expected to start", style="yellow")
        except subprocess.CalledProcessError:
            console.print("⚠️ Could not start development services. Make sure Docker is running.", style="yellow")
            console.print("You can start them manually with: make dev-up", style="dim")

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
    
    # Default to local Oxigraph in development
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
    

# ============================================================================
# AI Network Management Commands
# ============================================================================

def cmd_ai_network_list(args):
    """List all AI Network modules with their status"""
    try:
        from src.utils.ConfigLoader import get_ai_network_config
        
        config = get_ai_network_config()
        enabled_modules = config.get_enabled_modules()
        
        console.print("\n🤖 AI Network Module Status", style="bold cyan")
        console.print("=" * 50)
        
        for category, modules in enabled_modules.items():
            category_config = config.ai_network.get(category, {})
            category_enabled = category_config.get("enabled", False)
            
            status_icon = "✅ ENABLED" if category_enabled else "❌ DISABLED"
            console.print(f"\n📂 {category.upper().replace('_', ' ')} ({status_icon})", style="bold")
            console.print("-" * 30)
            
            if not category_enabled:
                console.print("   Category is disabled - no modules will load", style="dim")
                continue
                
            if not modules:
                console.print("   No enabled modules in this category", style="dim")
                continue
                
            for module in modules:
                name = module["name"]
                priority = module.get("priority", "N/A")
                description = module.get("description", "No description")
                console.print(f"   ✅ {name} (priority: {priority})", style="green")
                console.print(f"      {description}", style="dim")
        
        # Show disabled modules if requested
        if args.show_disabled:
            console.print(f"\n❌ DISABLED MODULES", style="bold red")
            console.print("-" * 30)
            
            for category, category_config in config.ai_network.items():
                if category == "loading":
                    continue
                    
                modules = category_config.get("modules", [])
                disabled_modules = [m for m in modules if not m.get("enabled", False)]
                
                if disabled_modules:
                    console.print(f"\n   {category}:", style="bold")
                    for module in disabled_modules:
                        name = module["name"]
                        description = module.get("description", "No description")
                        console.print(f"     ❌ {name} - {description}", style="red")
                        
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


def cmd_ai_network_enable(args):
    """Enable a specific AI Network module"""
    try:
        if not _update_module_status(args.module, args.category, True):
            sys.exit(1)
        
        console.print(f"✅ Enabled module '{args.module}' in category '{args.category}'", style="green")
        console.print("💡 Restart the application to apply changes", style="dim")
        
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


def cmd_ai_network_disable(args):
    """Disable a specific AI Network module"""
    try:
        if not _update_module_status(args.module, args.category, False):
            sys.exit(1)
        
        console.print(f"❌ Disabled module '{args.module}' in category '{args.category}'", style="yellow")
        console.print("💡 Restart the application to apply changes", style="dim")
        
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


def cmd_ai_network_validate(args):
    """Validate the AI Network configuration"""
    try:
        from src.utils.ConfigLoader import get_ai_network_config
        
        config = get_ai_network_config()
        issues = config.validate_configuration()
        
        if not issues:
            console.print("✅ AI Network configuration is valid", style="green")
            return
        
        console.print("❌ Configuration validation issues found:", style="red")
        for issue in issues:
            console.print(f"   - {issue}", style="red")
        
        sys.exit(1)
        
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


def cmd_ai_network_show(args):
    """Show the current AI Network configuration"""
    try:
        from src.utils.ConfigLoader import get_ai_network_config
        import yaml
        
        config = get_ai_network_config()
        
        console.print("\n🔧 AI Network Configuration", style="bold cyan")
        console.print("=" * 50)
        
        # Pretty print the ai_network section
        ai_network_config = config.ai_network
        config_yaml = yaml.dump({"ai_network": ai_network_config}, default_flow_style=False, indent=2)
        console.print(config_yaml)
        
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


def _update_module_status(module_name: str, category: str, enabled: bool) -> bool:
    """Update the enabled status of a module in the configuration file"""
    import yaml
    
    config_path = "config.yaml"
    
    try:
        # Read current configuration
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Navigate to the module
        ai_network = config.get("ai_network", {})
        category_config = ai_network.get(category, {})
        modules = category_config.get("modules", [])
        
        # Find and update the module
        module_found = False
        for module in modules:
            if module.get("name") == module_name:
                module["enabled"] = enabled
                module_found = True
                break
        
        if not module_found:
            console.print(f"❌ Module '{module_name}' not found in category '{category}'", style="red")
            console.print(f"💡 Available modules in {category}:", style="dim")
            for module in modules:
                console.print(f"   - {module.get('name')}", style="dim")
            return False
        
        # Write back to file
        with open(config_path, 'w') as file:
            yaml.dump(config, file, default_flow_style=False, indent=2)
        
        return True
        
    except Exception as e:
        console.print(f"❌ Error updating configuration: {e}", style="red")
        return False


# ============================================================================
# Agent Interaction Commands
# ============================================================================

def cmd_agent_chat(args):
    """Start interactive chat with ABI agent"""
    # Run the setup checks first
    for f in checks:
        f()
    
    # Set environment variables
    for key, value in dotenv_values().items():
        os.environ[key] = value
    
    os.environ['ENV'] = 'dev'  # Force development mode to avoid network calls
    
    # Ensure all development services are running
    ensure_dev_services_running()
    
    # Launch the terminal agent
    from src.core.apps.terminal_agent.main import generic_run_agent
    
    agent_name = args.agent if args.agent else "AbiAgent"
    console.print(f"🚀 Starting chat with {agent_name}...", style="cyan")
    generic_run_agent(agent_name)


def cmd_agent_list(args):
    """List available agents"""
    try:
        from src.__modules__ import get_modules
        
        console.print("\n🤖 Available Agents", style="bold cyan")
        console.print("=" * 30)
        
        modules = get_modules()
        agents_found = False
        
        for module in modules:
            # Look for agents in the module
            try:
                agents_dir = Path(module.module_path) / "agents"
                if agents_dir.exists():
                    for agent_file in agents_dir.glob("*Agent.py"):
                        if not agent_file.name.endswith("_test.py"):
                            agent_name = agent_file.stem
                            module_name = module.module_import_path.split(".")[-1]
                            console.print(f"  📋 {agent_name} (from {module_name})", style="green")
                            agents_found = True
            except Exception:
                continue
        
        if not agents_found:
            console.print("  No agents found", style="dim")
            
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


# ============================================================================
# System Commands
# ============================================================================

def cmd_system_status(args):
    """Show system status and health checks"""
    console.print("\n🔍 ABI System Status", style="bold cyan")
    console.print("=" * 30)
    
    # Check configuration
    try:
        from src.utils.ConfigLoader import get_ai_network_config
        config = get_ai_network_config()
        issues = config.validate_configuration()
        
        if not issues:
            console.print("✅ Configuration: Valid", style="green")
        else:
            console.print(f"❌ Configuration: {len(issues)} issues", style="red")
    except Exception as e:
        console.print(f"❌ Configuration: Error - {e}", style="red")
    
    # Check services
    oxigraph_url = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
    try:
        r = requests.get(f"{oxigraph_url}/query", params={"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"}, timeout=2)
        if r.status_code == 200:
            console.print("✅ Oxigraph: Running", style="green")
        else:
            console.print("❌ Oxigraph: Not responding", style="red")
    except:
        console.print("❌ Oxigraph: Not accessible", style="red")
    
    # Check modules
    try:
        from src.__modules__ import get_modules
        modules = get_modules()
        console.print(f"✅ Modules: {len(modules)} loaded", style="green")
    except Exception as e:
        console.print(f"❌ Modules: Error - {e}", style="red")


def cmd_system_setup(args):
    """Run initial system setup"""
    console.print("🚀 Running ABI system setup...", style="cyan")
    
    for f in checks:
        f()
    
    console.print("✅ Setup completed!", style="green")


# ============================================================================
# Main CLI Setup
# ============================================================================

def create_parser():
    """Create the main argument parser with subcommands"""
    parser = argparse.ArgumentParser(
        prog="abi",
        description="ABI - Artificial Business Intelligence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  abi chat                                    # Start interactive chat
  abi chat --agent ClaudeAgent              # Chat with specific agent
  abi agent list                             # List available agents
  abi network list                           # List AI Network modules
  abi network enable gemini core_models      # Enable Gemini model
  abi network disable claude core_models     # Disable Claude model
  abi network validate                       # Validate configuration
  abi system status                          # Show system status
  abi system setup                           # Run initial setup
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Chat command (default behavior)
    chat_parser = subparsers.add_parser('chat', help='Start interactive chat with ABI agent')
    chat_parser.add_argument('--agent', help='Specific agent to chat with')
    chat_parser.set_defaults(func=cmd_agent_chat)
    
    # Agent commands
    agent_parser = subparsers.add_parser('agent', help='Agent management commands')
    agent_subparsers = agent_parser.add_subparsers(dest='agent_command')
    
    agent_list_parser = agent_subparsers.add_parser('list', help='List available agents')
    agent_list_parser.set_defaults(func=cmd_agent_list)
    
    # AI Network commands
    network_parser = subparsers.add_parser('network', help='AI Network configuration management')
    network_subparsers = network_parser.add_subparsers(dest='network_command')
    
    # Network list
    network_list_parser = network_subparsers.add_parser('list', help='List all modules with their status')
    network_list_parser.add_argument('--show-disabled', action='store_true', help='Also show disabled modules')
    network_list_parser.set_defaults(func=cmd_ai_network_list)
    
    # Network enable
    network_enable_parser = network_subparsers.add_parser('enable', help='Enable a specific module')
    network_enable_parser.add_argument('module', help='Module name to enable')
    network_enable_parser.add_argument('category', help='Module category', 
                                      choices=['core_models', 'domain_experts', 'applications', 'custom_modules'])
    network_enable_parser.set_defaults(func=cmd_ai_network_enable)
    
    # Network disable
    network_disable_parser = network_subparsers.add_parser('disable', help='Disable a specific module')
    network_disable_parser.add_argument('module', help='Module name to disable')
    network_disable_parser.add_argument('category', help='Module category',
                                       choices=['core_models', 'domain_experts', 'applications', 'custom_modules'])
    network_disable_parser.set_defaults(func=cmd_ai_network_disable)
    
    # Network validate
    network_validate_parser = network_subparsers.add_parser('validate', help='Validate the configuration')
    network_validate_parser.set_defaults(func=cmd_ai_network_validate)
    
    # Network show
    network_show_parser = network_subparsers.add_parser('show', help='Show current configuration')
    network_show_parser.set_defaults(func=cmd_ai_network_show)
    
    # System commands
    system_parser = subparsers.add_parser('system', help='System management commands')
    system_subparsers = system_parser.add_subparsers(dest='system_command')
    
    system_status_parser = system_subparsers.add_parser('status', help='Show system status')
    system_status_parser.set_defaults(func=cmd_system_status)
    
    system_setup_parser = system_subparsers.add_parser('setup', help='Run initial system setup')
    system_setup_parser.set_defaults(func=cmd_system_setup)
    
    return parser


def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    # If no command specified, default to chat
    if not args.command:
        args.command = 'chat'
        args.func = cmd_agent_chat
        args.agent = None
    
    # Execute the command
    try:
        args.func(args)
    except KeyboardInterrupt:
        console.print("\n⚠️ Operation cancelled by user", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
