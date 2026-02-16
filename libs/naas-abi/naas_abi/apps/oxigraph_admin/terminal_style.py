from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.prompt import Prompt


console = Console()


def set_terminal_title():
    """Set the terminal window title"""
    try:
        print("\33]0;Oxigraph Admin\a", end="", flush=True)
    except Exception:
        pass


def print_welcome_message():
    """Print the welcome message for Oxigraph Admin"""
    set_terminal_title()

    title = Text("🔧 OXIGRAPH ADMIN", style="bold bright_cyan")
    subtitle = Text("Triple Store Administration & Monitoring", style="dim")

    content = Align.center(f"{title}\n{subtitle}")

    panel = Panel(
        content,
        border_style="bright_cyan",
        padding=(1, 2),
        title="[bold]ABI Infrastructure[/bold]",
        title_align="center",
    )

    console.print()
    console.print(panel)
    console.print()


def print_divider():
    """Print a visual divider"""
    console.print("─" * console.width, style="dim")
    console.print()


def print_status_info(text):
    """Print status information"""
    console.print(f"ℹ️  {text}", style="bright_blue")


def print_success_message(text):
    """Print success message"""
    console.print(f"✅ {text}", style="bright_green")


def print_error_message(text):
    """Print error message"""
    console.print(f"❌ {text}", style="bright_red")


def print_warning_message(text):
    """Print warning message"""
    console.print(f"⚠️  {text}", style="bright_yellow")


def print_menu_options(options):
    """Print menu options"""
    console.print("\n📋 Available Operations:", style="bold bright_white")
    for option in options:
        console.print(f"   {option}", style="white")
    console.print()


def get_user_input(prompt_text="Enter your choice"):
    """Get user input with styled prompt"""
    try:
        return Prompt.ask(f"[bold bright_cyan]>[/bold bright_cyan] {prompt_text}")
    except KeyboardInterrupt:
        console.print(
            "\n\n🛑 Ctrl+C pressed. Exiting Oxigraph Admin...", style="bright_red"
        )
        return "exit"
    except EOFError:
        return "exit"


def clear_screen():
    """Clear the terminal screen"""
    console.clear()


def print_health_status(healthy: bool, message: str):
    """Print health status with appropriate styling"""
    if healthy:
        console.print(f"🟢 Status: [bright_green]{message}[/bright_green]")
    else:
        console.print(f"🔴 Status: [bright_red]{message}[/bright_red]")


def print_container_info(container_data):
    """Print container information in a formatted way"""
    from rich.table import Table

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Container", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Ports", style="yellow")
    table.add_column("Created", style="blue")

    for container in container_data:
        name = container.get("Name", "Unknown")
        status = container.get("State", "Unknown")
        ports = container.get("Ports", "None")
        created = container.get("Created", "Unknown")

        # Add status emoji
        if status.lower() == "running":
            status = f"🟢 {status}"
        elif status.lower() == "exited":
            status = f"🔴 {status}"
        else:
            status = f"🟡 {status}"

        table.add_row(name, status, ports, created)

    console.print(table)


def print_performance_metrics(metrics):
    """Print performance metrics"""
    console.print("\n📊 Performance Metrics:", style="bold bright_white")

    for key, value in metrics.items():
        # Format different types of metrics
        if "time" in key.lower() or "latency" in key.lower():
            console.print(f"   ⏱️  {key}: [yellow]{value}ms[/yellow]")
        elif "count" in key.lower() or "total" in key.lower():
            console.print(f"   📈 {key}: [green]{value:,}[/green]")
        elif "memory" in key.lower() or "size" in key.lower():
            console.print(f"   💾 {key}: [blue]{value}[/blue]")
        else:
            console.print(f"   📋 {key}: [white]{value}[/white]")


def print_data_stats(stats):
    """Print data statistics"""
    console.print("\n📚 Data Statistics:", style="bold bright_white")

    for key, value in stats.items():
        if isinstance(value, int):
            console.print(f"   • {key}: [cyan]{value:,}[/cyan]")
        else:
            console.print(f"   • {key}: [white]{value}[/white]")


def confirmation_prompt(message: str, danger: bool = False) -> bool:
    """Get confirmation from user for potentially dangerous operations"""
    style = "bright_red" if danger else "bright_yellow"

    if danger:
        console.print(f"⚠️  [bold {style}]DANGER: {message}[/bold {style}]")
        response = Prompt.ask("Type 'YES' to confirm", default="NO")
        return response.upper() == "YES"
    else:
        console.print(f"❓ {message}")
        response = Prompt.ask("Continue?", choices=["y", "n"], default="n")
        return response.lower() == "y"
