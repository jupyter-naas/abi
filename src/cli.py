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
from dotenv import dotenv_values
import requests
import os
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

    console.print("\n" + "="*50, style="bright_blue")
    console.print("🤖 AI CONFIGURATION TIME!", style="bright_blue bold")
    console.print("="*50, style="bright_blue")
    
    console.print("\n💭 Time to choose your AI adventure!", style="bright_cyan")
    console.print("   🌐 Cloud models: OpenAI, Anthropic, etc. (Powerful, internet required)")
    console.print("   🏠 Local models: Ollama (Private, works offline)")
    
    prompt = Prompt.ask(
        "\n🎯 What's your choice", 
        choices=["Cloud", "Local"], 
        default="Cloud", 
        case_sensitive=False
    )
    
    prompt = prompt.lower()
    
    if prompt == "cloud":
        dv["AI_MODE"] = "cloud"
        console.print("☁️  Cloud mode selected! You chose... wisely! 🧙‍♂️", style="bright_cyan")
    else:
        dv["AI_MODE"] = "local"
        console.print("🏠 Local mode selected! Privacy first! 🔒", style="bright_cyan")
        
    if prompt == "cloud" and dv.get("OPENAI_API_KEY") is None:
        console.print("\n🗝️  We need your OpenAI API key to unlock the magic!", style="bright_yellow")
        console.print("💡 Tip: Get yours at https://platform.openai.com/api-keys", style="dim")
        
        openai_api_key = ""
        attempts = 0
        
        while openai_api_key == "":
            if attempts > 0:
                console.print("🤔 Hmm, that doesn't look right. Try again!", style="bright_red")
            
            openai_api_key = Prompt.ask("🔑 Enter your OpenAI API key")
            
            if not openai_api_key.startswith("sk-"):
                console.print("❌ Invalid API key format (should start with 'sk-')", style="bright_red")
                openai_api_key = ""
                attempts += 1
                
                if attempts >= 3:
                    console.print("🤷 Need help? Check out: https://help.openai.com/en/articles/4936850", style="bright_blue")
            
        loading_animation("🔐 Securing your API key...")
        with open(".env", "a") as f:
            f.write(f"\nOPENAI_API_KEY={openai_api_key}\n")
        console.print("✅ API key saved securely!", style="bright_green")
    
    with open(".env", "a") as f:
        f.write(f"\nAI_MODE={dv['AI_MODE']}\n")
    
    loading_animation("⚙️  Configuring AI mode...")
    console.print("✅ AI mode configured successfully!", style="bright_green")

def define_naas_api_key():
    dv = dotenv_values()
    
    if "NAAS_API_KEY" in dv:
        return
    
    console.print("\n" + "="*50, style="bright_magenta")
    console.print("🚀 NAAS INTEGRATION SETUP!", style="bright_magenta bold")
    console.print("="*50, style="bright_magenta")
    
    console.print("\n🎯 Time to connect to NAAS (Data & AI Platform)!", style="bright_cyan")
    console.print("📖 NAAS helps you automate your data workflows")
    
    naas_api_key = ""
    attempts = 0

    while naas_api_key == "":
        if attempts == 0:
            console.print("\n🔗 Get your API key here: https://naas.ai/account/api-key", style="bright_blue")
            console.print("💡 Pro tip: Copy it directly from your account page!", style="dim")
        
        naas_api_key = Prompt.ask("🗝️  Paste your NAAS API key here")
        
        loading_animation("🔍 Validating your API key...")
        
        try:
            r = requests.get("https://api.naas.ai/iam/apikey", headers={"Authorization": f"Bearer {naas_api_key}"})

            if r.status_code != 200:
                console.print("❌ Invalid API key. Let's try again!", style="bright_red")
                naas_api_key = ""
                attempts += 1
                
                if attempts >= 3:
                    console.print("🤷 Still having trouble? Contact support: https://naas.ai/support", style="bright_blue")
            else:
                console.print("✅ API key validated successfully!", style="bright_green")
                
        except requests.RequestException:
            console.print("⚠️  Network error. Please check your connection and try again.", style="bright_yellow")
            naas_api_key = ""
            attempts += 1

    loading_animation("💾 Saving your NAAS API key...")
    with open(".env", "a") as f:
        f.write(f"\nNAAS_API_KEY={naas_api_key}\n")
    
    console.print("✅ NAAS API key saved!", style="bright_green")

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
            console.print("🔴 Ollama is not running. Please start it and try again.", style="bright_red")
            console.print("💡 Tip: Run `ollama run deepseek-r1:8b` to start it.", style="dim")

            # Show how to install it
            console.print("💡 Tip: If it's not installed go to https://ollama.com/download to install it and run it.", style="dim")
        
        time.sleep(5)
    

checks = [
    define_abi_api_key,
    define_ai_mode,
    define_naas_api_key,
    ensure_ollama_running
]

def welcome_message():
    """Show an animated welcome message"""
    console.clear()
    
    # Animated ASCII art
    ascii_art = """
 █████╗ ██████╗ ██╗
██╔══██╗██╔══██╗██║
███████║██████╔╝██║
██╔══██║██╔══██╗██║
██║  ██║██████╔╝██║
╚═╝  ╚═╝╚═════╝ ╚═╝
    """
    
    console.print(Panel(
        Align.center(ascii_art),
        title="🚀 Welcome to ABI! 🚀",
        subtitle="✨ Let's release the AI! ✨",
        border_style="bright_blue",
        padding=(1, 2)
    ))
    
    # console.print("\n🎉 Welcome to the ABI Configuration Wizard!", style="bright_cyan bold")
    # console.print("🔧 We'll help you set up everything you need to get started!", style="bright_white")
    
    # # Fun loading animation
    # loading_animation("🎯 Preparing the setup wizard...")
    
    # console.print("\n💫 Here's what we'll configure:", style="bright_yellow")
    
    # # Create a nice table of what we'll do
    # table = Table(show_header=True, header_style="bold bright_blue")
    # table.add_column("🎯 Step", style="dim")
    # table.add_column("📋 Description", style="bright_white")
    # table.add_column("🎪 Status", style="bright_green")
    
    # table.add_row("1️⃣", "Generate ABI API Key", "🎲 Ready")
    # table.add_row("2️⃣", "Configure AI Mode", "🤖 Ready")
    # table.add_row("3️⃣", "Setup NAAS Integration", "🚀 Ready")
    
    # console.print(table)
    
    # if not Confirm.ask("\n🎊 Ready to start the configuration party?", default=True):
    #     console.print("👋 See you next time! Configuration wizard is always here when you need it.", style="bright_cyan")
    #     exit(0)

def completion_message():
    """Show completion message with summary"""
    console.print("\n" + "="*60, style="bright_green")
    console.print("🎊 CONFIGURATION COMPLETE! 🎊", style="bright_green bold")
    console.print("="*60, style="bright_green")
    
    celebration_message()
    
    # Show summary
    console.print("\n📊 Configuration Summary:", style="bright_cyan bold")
    
    dv = dotenv_values()
    summary_table = Table(show_header=True, header_style="bold bright_blue")
    summary_table.add_column("🏷️  Setting", style="dim")
    summary_table.add_column("✅ Status", style="bright_green")
    summary_table.add_column("💡 Value", style="bright_white")
    
    summary_table.add_row("ABI API Key", "✅ Configured", "🎲 Generated")
    summary_table.add_row("AI Mode", "✅ Configured", f"🤖 {dv.get('AI_MODE', 'Unknown').title()}")
    summary_table.add_row("NAAS API Key", "✅ Configured", "🔑 Validated")
    
    console.print(summary_table)
    
    # Next steps
    console.print("\n🚀 What's Next?", style="bright_yellow bold")
    console.print("• 📖 Check out the documentation")
    console.print("• 🏃‍♂️ Start using ABI with your configured settings")
    console.print("• 🎯 Build amazing AI-powered applications!")
    
    console.print("\n💝 Thank you for using ABI! Happy coding! 🎉", style="bright_magenta")

def agent_selection():
    console.print("🔍 Loading agents...")
    from src.core.apps.terminal_agent.main import generic_run_agent
    generic_run_agent("SupervisorAgent")
    return 
    

def main():
    welcome_message()
        
    for i, check in enumerate(checks):
        check()

    agent_selection()

if __name__ == "__main__":
    main()
