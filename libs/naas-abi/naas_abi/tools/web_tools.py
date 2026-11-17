"""ABI web_search and web_fetch.

Office-agent search stack: ddgs, no API key, year hint, HTML to text.
"""

from __future__ import annotations

import re
import urllib.parse
from contextvars import ContextVar

from langchain_core.tools import tool
from naas_abi_core.utils import outbound

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; ABISlides/1.0; +https://github.com/jupyter-naas/abi)"
)
_MAX_FETCH_BYTES = 200_000
_REQUEST_TIMEOUT = 15
# Truncated search-result URLs. Qwen retries them until the 160-step cap.
_TRUNCATED_URL_RE = re.compile(r"[\u2026\u2025\u22ef]|\.\.\.")
MAX_WEB_FETCHES = 4
_web_fetch_urls: ContextVar[list[str] | None] = ContextVar(
    "web_fetch_urls", default=None
)
_web_search_queries: ContextVar[list[str] | None] = ContextVar(
    "web_search_queries", default=None
)
_REPEAT_FETCH_MESSAGE = (
    "web_fetch already ran on this URL this turn. Stop and reply. "
    "Do not call web_fetch again. If a document is open, fill it with "
    "one fill_document_slots call, then reply."
)
_TRUNCATED_URL_MESSAGE = (
    "This URL is truncated (ellipsis). Do not retry it. "
    "Stop fetching. If a document is open, fill it with one "
    "fill_document_slots call, then reply."
)
_FETCH_AFTER_WRITE_MESSAGE = (
    "A document write already ran this turn. Stop and reply. "
    "Do not call web_fetch or web_search again."
)
_FETCH_BUDGET_MESSAGE = (
    f"web_fetch budget reached ({MAX_WEB_FETCHES} URLs this turn). "
    "Stop fetching. If a document is open, fill it with one "
    "fill_document_slots call, then reply."
)
_REPEAT_SEARCH_MESSAGE = (
    "web_search already ran this query this turn. Stop searching. "
    "If a document is open, fill it with one fill_document_slots call, "
    "then reply."
)


def reset_web_tool_turn() -> None:
    """Clear per-turn fetch/search locks. Tests and request setup call this."""
    _web_fetch_urls.set([])
    _web_search_queries.set([])


def _normalize_fetch_url(url: str) -> str:
    parsed = urllib.parse.urlparse((url or "").strip())
    return urllib.parse.urlunparse(
        (
            (parsed.scheme or "").lower(),
            (parsed.netloc or "").lower(),
            parsed.path or "",
            "",
            parsed.query or "",
            "",
        )
    )


def _url_is_truncated(url: str) -> bool:
    return bool(_TRUNCATED_URL_RE.search(url or ""))


def _noted_fetch_urls() -> list[str]:
    bucket = _web_fetch_urls.get()
    if bucket is None:
        bucket = []
        _web_fetch_urls.set(bucket)
    return bucket


def _note_fetch_url(url: str) -> None:
    key = _normalize_fetch_url(url)
    bucket = _noted_fetch_urls()
    if key and key not in bucket:
        bucket.append(key)


def _noted_search_queries() -> list[str]:
    bucket = _web_search_queries.get()
    if bucket is None:
        bucket = []
        _web_search_queries.set(bucket)
    return bucket


def _note_search_query(query: str) -> None:
    key = (query or "").strip().lower()
    bucket = _noted_search_queries()
    if key and key not in bucket:
        bucket.append(key)


def _documents_write_ran() -> bool:
    from naas_abi_core.services.agent.context import documents_writes_completed

    return bool(documents_writes_completed.get())


def _documents_turn() -> bool:
    from naas_abi_core.services.agent.context import documents_turn_active

    return documents_turn_active()


def reject_web_fetch(url: str) -> str | None:
    """Refuse a truncated URL, a repeat URL, a fetch after write, or a 5th fetch."""
    if _documents_write_ran():
        return _FETCH_AFTER_WRITE_MESSAGE
    key = _normalize_fetch_url(url)
    seen = _noted_fetch_urls()
    if key and key in seen:
        return _REPEAT_FETCH_MESSAGE
    if _url_is_truncated(url):
        _note_fetch_url(url)
        return _TRUNCATED_URL_MESSAGE
    if _documents_turn() and len(seen) >= MAX_WEB_FETCHES:
        return _FETCH_BUDGET_MESSAGE
    return None


def reject_web_search(query: str) -> str | None:
    """Refuse the same search query twice, or search after a document write."""
    if _documents_write_ran():
        return _FETCH_AFTER_WRITE_MESSAGE
    key = (query or "").strip().lower()
    if key and key in _noted_search_queries():
        return _REPEAT_SEARCH_MESSAGE
    return None


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
    except Exception as exc:  # noqa: BLE001  # re-raised as RuntimeError below
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


def _refused_message(url: str, reason: str) -> str:
    return (
        f"Error: web_fetch opens public http:// and https:// pages only, and it "
        f"will not open '{url}': {reason}. Nothing there is public research "
        f"material. Do not retry it under another spelling."
    )


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
        blocked = reject_web_fetch(url)
        if blocked is not None:
            return blocked
        _note_fetch_url(url)
        try:
            response = outbound.fetch(
                url,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "text/html,text/plain,*/*",
                },
                max_bytes=_MAX_FETCH_BYTES,
                timeout=_REQUEST_TIMEOUT,
            )
        except outbound.OutboundRefused as exc:
            return _refused_message(url, str(exc))
        except outbound.OutboundError as exc:
            return f"Could not reach '{url}': {exc}"
        if response.status_code >= 400:
            return f"HTTP {response.status_code} error fetching '{url}'"

        content_type = response.headers.get("content-type", "")
        text = response.text()

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
        blocked = reject_web_search(query)
        if blocked is not None:
            return blocked
        _note_search_query(query)
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
        shown = 0
        for row in results:
            title = row.get("title") or row.get("t") or ""
            url = row.get("href") or row.get("url") or row.get("u") or ""
            snippet = row.get("body") or row.get("snippet") or row.get("d") or ""
            if url and _url_is_truncated(url):
                continue
            shown += 1
            lines.append(f"{shown}. **{title}**")
            if url:
                lines.append(f"   {url}")
            if snippet:
                lines.append(f"   {snippet[:250]}")
            lines.append("")

        return "\n".join(lines)

    return web_search
