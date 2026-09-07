import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

from naas_abi.agents.tools.web_tools import (
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
