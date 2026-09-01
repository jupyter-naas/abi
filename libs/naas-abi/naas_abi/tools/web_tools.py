"""ABI web_search and web_fetch.

Ported from the zen WebTools wrapper (ddgs, no API key, year hint, HTML to
text). This is the shared search stack. Agents import it from ``naas_abi.tools``.
Do not import ``zen.tools.WebTools`` from ABI.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request

from langchain_core.tools import tool

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; ABISlides/1.0; +https://github.com/jupyter-naas/abi)"
)
_MAX_FETCH_BYTES = 200_000
_REQUEST_TIMEOUT = 15


def _ddgs_search(query: str, max_results: int) -> list[dict]:
    """Use ddgs (preferred) with fallback to duckduckgo_search.

    Raises RuntimeError when the dependency is missing or the backend fails.
    Callers must not treat that as empty results.
    """
    last_error: Exception | None = None
    try:
        from ddgs import DDGS

        return list(DDGS().text(query, max_results=max_results)) or []
    except ImportError as exc:
        last_error = exc
    except Exception as exc:
        last_error = exc
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from duckduckgo_search import DDGS as DDGS2

            return list(DDGS2().text(query, max_results=max_results)) or []
    except ImportError as exc:
        raise RuntimeError(
            "web_search requires the 'ddgs' package. Install with: uv add ddgs"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"web_search failed: {exc}") from exc
    if last_error is not None:
        raise RuntimeError(f"web_search failed: {last_error}") from last_error
    return []


def _html_to_text(html: str) -> str:
    """Lightweight HTML to plain text. No extra dependencies."""
    html = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r"<(br|p|div|h[1-6]|li|tr|blockquote)[^>]*>",
        "\n",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r"<[^>]+>", " ", html)
    for entity, char in [
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&nbsp;", " "),
        ("&quot;", '"'),
        ("&#39;", "'"),
    ]:
        html = html.replace(entity, char)
    html = re.sub(r"\n{3,}", "\n\n", html)
    html = re.sub(r"[ \t]{2,}", " ", html)
    return html.strip()


def make_web_fetch_tool(user_agent: str = _DEFAULT_USER_AGENT):
    """Return a tool that fetches a URL and returns readable text."""

    @tool
    def web_fetch(url: str, max_length: int = 5000) -> str:
        """Fetch a URL and return its content as plain text.

        Strips HTML tags. Use after web_search when you need the page body.

        Args:
            url: Full http or https URL.
            max_length: Maximum characters to return (default 5000).
        """
        if not url.startswith(("http://", "https://")):
            return f"Error: URL must start with http:// or https://  Got: '{url}'"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": user_agent, "Accept": "text/html,text/plain,*/*"},
            )
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                raw = resp.read(_MAX_FETCH_BYTES)
                content_type = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            return f"HTTP {exc.code} error fetching '{url}': {exc.reason}"
        except urllib.error.URLError as exc:
            return f"Could not reach '{url}': {exc.reason}"
        except Exception as exc:  # noqa: BLE001
            return f"Error fetching '{url}': {exc}"

        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        try:
            text = raw.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = raw.decode("utf-8", errors="replace")

        if "html" in content_type.lower() or text.lstrip().startswith("<"):
            text = _html_to_text(text)

        text = text[:max_length]
        if len(text) == max_length:
            text += f"\n\n... [truncated at {max_length} characters]"

        return text.strip()

    return web_fetch


def make_web_search_tool(user_agent: str = _DEFAULT_USER_AGENT):
    """Return a tool that searches the web via DuckDuckGo (ddgs). No API key."""
    del user_agent

    @tool
    def web_search(query: str, max_results: int = 8) -> str:
        """Search the web and return titles, URLs, and short descriptions.

        Uses DuckDuckGo via ddgs (no API key). For a specific page, follow up
        with web_fetch.

        Always include the current year in time-sensitive queries
        (e.g. "president of the US 2026").

        Args:
            query: Search query string.
            max_results: Number of results (default 8, max 20).
        """
        max_results = min(max(1, max_results), 20)

        try:
            results = _ddgs_search(query, max_results)
        except RuntimeError as exc:
            return f"Error: {exc}"

        if not results:
            return (
                f"No results found for '{query}'. "
                "Try rephrasing or using web_fetch on a known URL."
            )

        lines = [f'Search results for: "{query}"\n']
        for i, row in enumerate(results, 1):
            title = row.get("title") or row.get("t") or ""
            url = row.get("href") or row.get("url") or row.get("u") or ""
            snippet = row.get("body") or row.get("snippet") or row.get("d") or ""
            lines.append(f"{i}. **{title}**")
            if url:
                lines.append(f"   {url}")
            if snippet:
                lines.append(f"   {snippet[:250]}")
            lines.append("")

        return "\n".join(lines)

    return web_search
