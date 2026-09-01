from unittest.mock import MagicMock, patch

from naas_abi.agents.tools.web_tools import (
    _html_to_text,
    make_web_fetch_tool,
    make_web_search_tool,
)


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
