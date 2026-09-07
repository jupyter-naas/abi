import tomllib
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from naas_abi.agents.tools.web_tools import (
    _ddgs_search,
    _html_to_text,
    make_web_fetch_tool,
    make_web_search_tool,
)

_PYPROJECT = Path(__file__).parents[3] / "pyproject.toml"


def test_html_to_text_strips_tags_and_scripts() -> None:
    assert "<" not in _html_to_text("<p>Hello <b>world</b></p>")
    assert "Hello" in _html_to_text("<p>Hello <b>world</b></p>")
    assert "alert" not in _html_to_text("<script>alert('xss')</script><p>Safe</p>")
    assert "Safe" in _html_to_text("<script>alert('xss')</script><p>Safe</p>")
    assert "Rock & Roll" in _html_to_text("Rock &amp; Roll")
    assert "color" not in _html_to_text("<style>.foo{color:red}</style><p>Visible</p>")
    assert "Visible" in _html_to_text("<style>.foo{color:red}</style><p>Visible</p>")
    assert "\n" in _html_to_text("<h1>Title</h1><p>Body</p>")


def test_web_search_tool_name_and_numbered_results() -> None:
    tool = make_web_search_tool()
    assert tool.name == "web_search"
    fake = [
        {"title": "Trump wins", "href": "https://bbc.com/1", "body": "Donald Trump..."},
        {"title": "White House", "href": "https://whitehouse.gov", "body": "President..."},
    ]
    with patch("naas_abi.agents.tools.web_tools._ddgs_search", return_value=fake):
        result = tool.invoke({"query": "president usa 2026"})
    assert "1." in result
    assert "Trump wins" in result
    assert "bbc.com" in result


def test_web_search_empty_and_caps() -> None:
    tool = make_web_search_tool()
    with patch("naas_abi.agents.tools.web_tools._ddgs_search", return_value=[]) as mock:
        empty = tool.invoke({"query": "xyzzy nothing here"})
        assert "No results" in empty
        assert "web_fetch" in empty
        tool.invoke({"query": "q", "max_results": 999})
        mock.assert_called_with("q", 20)


def test_web_fetch_rejects_non_http_and_strips_html() -> None:
    tool = make_web_fetch_tool()
    assert tool.name == "web_fetch"
    assert "Error" in tool.invoke({"url": "ftp://example.com/file"})

    html = b"<html><body><p>Hello world</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.read.return_value = html
    mock_resp.headers.get.return_value = "text/html; charset=utf-8"
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch(
        "naas_abi.agents.tools.web_tools.urllib.request.urlopen",
        return_value=mock_resp,
    ):
        result = tool.invoke({"url": "https://example.com"})
    assert "Hello world" in result
    assert "<p>" not in result


def test_web_search_reaches_the_ddgs_backend() -> None:
    """web_search must render results, not the missing-dependency message.

    The tests above stub _ddgs_search, so they pass whether or not ddgs is
    installed. That is how a bare install shipped a web_search that only ever
    answered "web_search requires the 'ddgs' package" while the suite was
    green. This one stubs the backend one layer lower, at ddgs.DDGS, so the
    real guard in _ddgs_search runs and the import has to resolve.

    No live query: DuckDuckGo rate-limits and CI egress is not guaranteed, so a
    network assertion would fail for reasons that have nothing to do with the
    dependency. Reaching the backend is the boundary that the dependency owns.
    """
    backend = MagicMock()
    backend.return_value.text.return_value = iter(
        [{"title": "Naas", "href": "https://naas.ai", "body": "Ontology platform"}]
    )
    with patch("ddgs.DDGS", backend):
        result = make_web_search_tool().invoke({"query": "naas ai", "max_results": 3})

    assert "ddgs" not in result
    assert "Naas" in result
    assert "https://naas.ai" in result
    backend.return_value.text.assert_called_once_with("naas ai", max_results=3)


def test_ddgs_is_a_required_dependency_of_naas_abi() -> None:
    """ddgs belongs in the main dependency set, not an extra and not the venv.

    AbiAgent.tools() calls slides_research_tools() with no feature flag, so
    every agent binds web_search. A default install that cannot run it is the
    bug. Reading the pyproject rather than the environment is deliberate: the
    test above passes on any machine that happens to have ddgs from another
    package, and would keep passing if this declaration were deleted.
    """
    project = tomllib.loads(_PYPROJECT.read_text())["project"]
    names = [dep.split(">")[0].split("[")[0].strip() for dep in project["dependencies"]]

    assert "ddgs" in names
    assert "ddgs" not in str(project.get("optional-dependencies", {}))


def test_ddgs_search_raises_when_no_backend_is_importable() -> None:
    """A missing backend must raise, not return an empty list.

    An empty list reads as "the web has nothing on this", which is a claim the
    function is in no position to make, and web_search renders it as a
    "No results found" the model then reports as fact.
    """
    missing = {"ddgs": None, "duckduckgo_search": None}
    with (
        patch.dict("sys.modules", missing),
        pytest.raises(RuntimeError, match="requires the 'ddgs' package"),
    ):
        _ddgs_search("anything", max_results=3)


def test_ddgs_search_falls_back_when_ddgs_fails() -> None:
    broken = MagicMock()
    broken.DDGS.side_effect = Exception("ddgs broken")
    spare = MagicMock()
    spare.DDGS.return_value.text.return_value = iter(
        [{"title": "Fallback", "href": "https://fallback.com", "body": "B"}]
    )

    with patch.dict("sys.modules", {"ddgs": broken, "duckduckgo_search": spare}):
        results = _ddgs_search("test", max_results=1)

    assert results[0]["title"] == "Fallback"


def test_web_search_floors_max_results_at_one() -> None:
    tool = make_web_search_tool()
    with patch("naas_abi.agents.tools.web_tools._ddgs_search", return_value=[]) as mock:
        tool.invoke({"query": "q", "max_results": 0})
    mock.assert_called_once_with("q", 1)


def test_web_search_truncates_snippets_and_tolerates_other_key_names() -> None:
    tool = make_web_search_tool()
    long_body = [{"title": "T", "href": "https://example.com", "body": "X" * 500}]
    with patch("naas_abi.agents.tools.web_tools._ddgs_search", return_value=long_body):
        assert "X" * 251 not in tool.invoke({"query": "q"})

    short_keys = [{"t": "Title", "u": "https://x.com", "d": "Desc"}]
    with patch("naas_abi.agents.tools.web_tools._ddgs_search", return_value=short_keys):
        assert "Title" in tool.invoke({"query": "q"})


def test_web_fetch_marks_truncated_pages() -> None:
    tool = make_web_fetch_tool()
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"A" * 10_000
    mock_resp.headers.get.return_value = "text/plain"
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch(
        "naas_abi.agents.tools.web_tools.urllib.request.urlopen",
        return_value=mock_resp,
    ):
        result = tool.invoke({"url": "https://x.com", "max_length": 100})

    assert "truncated" in result
    assert len(result) <= 200


def test_web_fetch_reports_transport_failures_as_text() -> None:
    """Returned, not raised: the caller is a model reading a tool result."""
    tool = make_web_fetch_tool()
    http_error = urllib.error.HTTPError(
        url="https://x.com", code=404, msg="Not Found", hdrs=MagicMock(), fp=None
    )
    with patch("urllib.request.urlopen", side_effect=http_error):
        assert "404" in tool.invoke({"url": "https://x.com/missing"})

    unreachable = urllib.error.URLError("Name not resolved")
    with patch("urllib.request.urlopen", side_effect=unreachable):
        assert "Could not reach" in tool.invoke({"url": "https://nonexistent.invalid"})
