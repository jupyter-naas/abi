from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.box import ROUNDED
import os
import platform

console = Console()

def set_terminal_title():
    """Set the terminal title to 'ABI'"""
    if platform.system() == "Windows":
        os.system("title ABI")
    else:  # For Unix-like systems (Linux, macOS)
        print('\33]0;ABI\a', end='', flush=True)

def print_assistant_response(text):
    console.print()  # Add a blank line before the assistant's response
    console.print("[bold green]Abi:[/bold green] ", end="")
    md = Markdown(text)
    console.print(md)
    console.print()  # Add a blank line after the assistant's response

def print_system_message(text):
    console.print()  # Add a blank line before the system message
    system_text = Text(text, style="yellow")
    console.print(Panel(system_text, border_style="yellow", box=ROUNDED, expand=False, title="System", title_align="left"))
    console.print()  # Add a blank line after the system message

def print_code(code, language="python"):
    syntax = Syntax(code, language, theme="monokai", line_numbers=True)
    console.print(Panel(syntax, border_style="red", box=ROUNDED, expand=False, title=f"Code ({language})", title_align="left"))

def print_tool_usage(tool_name):
    console.print(f"\n🔧 [bold blue]Tool Used:[/bold blue] {tool_name}")

def clear_screen():
    console.clear()

def print_welcome_message():
    # Set terminal title
    set_terminal_title()
    
    welcome_text = Text.assemble(
        ("Welcome to ABI Super Assistant\n\n", "bold green"),
        ("Available commands:\n", "yellow"),
        ("- ", "dim"), ("'exit' ", "cyan"), ("to end the conversation\n", "dim"),
        ("- ", "dim"), ("'reset' ", "cyan"), ("to start a new conversation\n", "dim"),
        ("- ", "dim"), ("'help' ", "cyan"), ("to see these commands again", "dim")
    )
    console.print(Panel(welcome_text, expand=False))
    console.print()

def print_divider():
    console.print("─" * console.width, style="dim")

def get_user_input():
    user_input = console.input("\n[bold cyan]You:[/bold cyan] ")  # Add a newline before the prompt
    console.print()  # Add a blank line after the user's input
    return user_input
