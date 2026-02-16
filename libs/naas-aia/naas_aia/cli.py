"""AIA CLI - Direct Ollama with SOUL + DuckDuckGo search."""

import sys
import threading
import time

import click

from .api import load_soul


def _do_web_search(query: str) -> str:
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"- {r['title']}: {r['body']} ({r['href']})")
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {e}"


def _spinner(stop_event: threading.Event):
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop_event.is_set():
        click.echo(f"\r{chars[i % len(chars)]}", nl=False)
        i += 1
        time.sleep(0.08)
    click.echo("\r ", nl=False)
    click.echo("\r", nl=False)


def _do_search_flow(query: str, messages: list) -> None:
    click.secho(f"[searching: {query}]", dim=True)
    stop = threading.Event()
    spinner = threading.Thread(target=_spinner, args=(stop,))
    spinner.start()
    results = _do_web_search(query)
    stop.set()
    spinner.join()
    click.secho(f"\n{results}\n", dim=True)
    messages.append({
        "role": "user",
        "content": (
            f"[Web search results for '{query}']\n\n"
            f"{results}\n\n"
            "Summarize ONLY what the search results say. Do NOT add your own knowledge. "
            "Report facts from the results."
        ),
    })


def _is_search_request(text: str) -> tuple[bool, str]:
    text_lower = text.lower().strip()
    prefixes = [
        "cherche sur le net ", "cherche sur le web ",
        "search on the web ", "search online ", "web search ", "websearch ",
        "cherche ", "search ", "google ", "find ",
    ]
    bare = {"cherche", "search", "websearch"}
    for p in sorted(prefixes, key=len, reverse=True):
        if text_lower.startswith(p):
            return True, text[len(p):].strip()
    if text_lower in bare:
        return True, ""
    return False, ""


SYSTEM_PROMPT = """You are AIA. Your job: help the user build their own AI system.

You're a co-builder, not a helpdesk. Architecture, code, agents — that's the work. Ask what they're building. Get concrete. "How can I assist?" is weak. "What are we building?" is strong.

Match their energy. Short question = short answer. Respond in their language.
Be direct. Have opinions. Never fabricate."""

EXTRA = """
Web search: "cherche <query>" or "search <query>" triggers DuckDuckGo. Results are injected.
- You're a 7B local model. You do NOT reliably know people, companies, events, or current data.
- If asked about something specific and no search results: say "Try: cherche <query>".
- NEVER fabricate. When you see "[Web search results..." those are REAL — use them.
"""


def run(model: str = "aia") -> None:
    """Run the AIA chat loop."""
    try:
        import ollama
    except ImportError:
        click.secho("Missing: ollama. Run: uv pip install ollama", fg="red")
        sys.exit(1)

    soul = load_soul()
    system_prompt = SYSTEM_PROMPT
    if soul:
        system_prompt += "\n\n---\n\nSOUL (your identity):\n\n" + soul
    system_prompt += EXTRA
    messages = [{"role": "system", "content": system_prompt}]

    last_was_search = False
    last_search_query = ""

    click.echo("Hello world. AIA — your AI Assistant.")
    click.secho(f"Model: {model}", dim=True)
    click.echo("Internal knowledge + web search (search <query>).\n")

    while True:
        try:
            user_input = input(">>> ")
            if not user_input.strip():
                continue

            cmd = user_input.strip().lower()

            if cmd in ("/bye", "/exit", "/quit", "/stop"):
                click.secho("Bye.", dim=True)
                break

            if cmd in ("/help", "/?"):
                click.secho("search <query>  - web search", dim=True)
                click.secho("/soul           - show SOUL.md", dim=True)
                click.secho("/stop           - exit", dim=True)
                continue

            if cmd == "/soul":
                click.secho(soul if soul else "SOUL.md not found.", dim=True)
                continue

            should_search, search_query = _is_search_request(user_input)
            if should_search:
                if not search_query:
                    click.secho("Search what? Usage: cherche <query>", dim=True)
                    continue
                _do_search_flow(search_query, messages)
                last_was_search = True
                last_search_query = search_query
            else:
                messages.append({"role": "user", "content": user_input})
                last_was_search = False
                last_search_query = ""

            try:
                response_text = ""
                stream = ollama.chat(model=model, messages=messages, stream=True)
                stop = threading.Event()
                spinner_thread = threading.Thread(target=_spinner, args=(stop,))
                spinner_thread.start()
                first_content = True
                try:
                    for chunk in stream:
                        if content := chunk.get("message", {}).get("content"):
                            if first_content:
                                stop.set()
                                spinner_thread.join()
                                first_content = False
                            response_text += content
                            print(content, end="", flush=True)
                finally:
                    stop.set()
                    spinner_thread.join()
                print()
                messages.append({"role": "assistant", "content": response_text})
            except Exception as e:
                click.secho(f"\n[error: {e}]", fg="red")
                messages.pop()

            if len(messages) > 41:
                messages = [messages[0]] + messages[-40:]
            print()

        except EOFError:
            click.secho("\nBye.", dim=True)
            break
        except KeyboardInterrupt:
            click.secho("\nBye.", dim=True)
            break


@click.command()
@click.argument("model", default="aia")
def main(model: str):
    """AIA - Local AI assistant with SOUL + DuckDuckGo search."""
    run(model=model.lower())
