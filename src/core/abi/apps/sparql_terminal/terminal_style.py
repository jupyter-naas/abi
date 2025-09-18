from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED
import os
import platform
import readline
import atexit

console = Console()

# Command history for arrow key navigation
command_history = []
history_index = 0
current_input = ""


def set_terminal_title():
    """Set the terminal title to 'SPARQL Terminal'"""
    if platform.system() == "Windows":
        os.system("title SPARQL Terminal")
    else:  # For Unix-like systems (Linux, macOS)
        print("\33]0;SPARQL Terminal\a", end="", flush=True)


def print_query_result(result):
    """Print SPARQL query results from RDFLib's Graph().query() which returns a SPARQLResult object"""
    if not result:
        console.print("[yellow]No results found[/yellow]")
        return

    # Create a table
    table = Table(show_header=True, header_style="bold magenta", box=ROUNDED)

    # Get variables from the result
    variables = result.vars

    # Add columns
    for var in variables:
        table.add_column(str(var))

    # Add rows
    for row in result:
        row_values = []
        for var in variables:
            value = str(row[var]) if row[var] is not None else ""
            row_values.append(value)
        table.add_row(*row_values)

    console.print(table)


def print_query_error(error):
    """Print SPARQL query error in a formatted panel"""
    console.print(
        Panel(
            f"[red]Error executing SPARQL query:[/red]\n{str(error)}",
            border_style="red",
            box=ROUNDED,
            expand=False,
            title="Query Error",
            title_align="left",
        )
    )


def print_system_message(text):
    console.print()
    system_text = Text(text, style="yellow")
    console.print(
        Panel(
            system_text,
            border_style="yellow",
            box=ROUNDED,
            expand=False,
            title="System",
            title_align="left",
        )
    )
    console.print()


def print_query(query):
    """Print the SPARQL query with syntax highlighting"""
    syntax = Syntax(query, "sparql", theme="monokai", line_numbers=True)
    console.print(
        Panel(
            syntax,
            border_style="blue",
            box=ROUNDED,
            expand=False,
            title="SPARQL Query",
            title_align="left",
        )
    )


def clear_screen():
    console.clear()


def print_welcome_message():
    # Set terminal title
    set_terminal_title()

    welcome_text = Text.assemble(
        ("Welcome to SPARQL Terminal\n\n", "bold green"),
        ("Available commands:\n", "yellow"),
        ("- ", "dim"),
        ("'exit' ", "cyan"),
        ("to end the session\n", "dim"),
        ("- ", "dim"),
        ("'help' ", "cyan"),
        ("to see these commands again\n", "dim"),
        ("- ", "dim"),
        ("'clear' ", "cyan"),
        ("to clear the screen\n", "dim"),
        ("- ", "dim"),
        ("Enter your SPARQL query ", "cyan"),
        ("to execute it\n", "dim"),
        ("\nMultiline input:\n", "yellow"),
        ("- ", "dim"),
        ("End each line with ", "cyan"),
        ("';' ", "bold"),
        ("to continue\n", "dim"),
        ("- ", "dim"),
        ("Press ", "cyan"),
        ("Enter ", "bold"),
        ("twice to finish\n", "dim"),
        ("\nNavigation:\n", "yellow"),
        ("- ", "dim"),
        ("Use ", "cyan"),
        ("↑/↓ ", "bold"),
        ("arrow keys to navigate command history", "dim"),
    )
    console.print(Panel(welcome_text, expand=False))
    console.print()


def print_divider():
    console.print("─" * console.width, style="dim")


def preinput():
    """Save the current input before displaying a history item"""
    global current_input
    current_input = readline.get_line_buffer()
    return current_input


def get_user_input():
    """Get user input with support for multiline SPARQL queries and command history.
    Use ';' at the end of a line to terminate the query."""
    global command_history, history_index, current_input

    try:
        lines = []

        # Use a simpler approach for history navigation
        # This avoids the issue with the letter 'b' being captured
        readline.set_history_length(1000)  # Set history length

        while True:
            # Get input with history support
            line = console.input("\n[bold cyan]SPARQL>[/bold cyan] ")

            # Handle special commands
            if line.lower() in ["exit", "help", "clear"]:
                if line not in command_history:
                    command_history.append(line)
                return line.lower()

            # Add the line to our collection
            lines.append(line)

            # If the line ends with a semicolon, we're done
            if line.strip().endswith(";"):
                break

            # If the line is empty and we have content, we're done
            if not line.strip() and lines:
                break

        # Join the lines and remove the trailing semicolon
        query = " ".join(lines).strip()
        if query.endswith(";"):
            query = query[:-1].strip()

        # Add to history if it's not empty
        if query and query not in command_history:
            command_history.append(query)

        console.print()
        return query
    except EOFError:
        console.print("\n[bold red]Session ended by user.[/bold red]")
        return "exit"
    except KeyboardInterrupt:
        console.print("\n[bold red]Session ended by user.[/bold red]")
        return "exit"


# Save command history when exiting
def save_history():
    """Save command history to a file"""
    history_file = os.path.expanduser("~/.sparql_terminal_history")
    try:
        with open(history_file, "w") as f:
            for cmd in command_history:
                f.write(cmd + "\n")
    except Exception:
        pass


# Load command history when starting
def load_history():
    """Load command history from a file"""
    global command_history
    history_file = os.path.expanduser("~/.sparql_terminal_history")
    try:
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                command_history = [
                    line.strip() for line in f.readlines() if line.strip()
                ]
    except Exception:
        pass


# Register the save_history function to run at exit
atexit.register(save_history)

# Load history when the module is imported
load_history()
