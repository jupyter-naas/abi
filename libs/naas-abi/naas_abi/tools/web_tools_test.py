import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from naas_abi_core.utils.outbound import FetchedResponse

from naas_abi.tools.web_tools import (
    _ddgs_search,
    _html_to_text,
    make_web_fetch_tool,
    make_web_search_tool,
    reset_web_tool_turn,
)


@pytest.fixture(autouse=True)
def _reset_web_tool_turn() -> None:
    reset_web_tool_turn()


_PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"


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
        {
            "title": "White House",
            "href": "https://whitehouse.gov",
            "body": "President...",
        },
    ]
    with patch("naas_abi.tools.web_tools._ddgs_search", return_value=fake):
        result = tool.invoke({"query": "president usa 2026"})
    assert "1." in result
    assert "Trump wins" in result
    assert "bbc.com" in result


def test_web_search_empty_and_caps() -> None:
    tool = make_web_search_tool()
    with patch("naas_abi.tools.web_tools._ddgs_search", return_value=[]) as mock:
        empty = tool.invoke({"query": "xyzzy nothing here"})
        assert "No results" in empty
        assert "web_fetch" in empty
        tool.invoke({"query": "q", "max_results": 999})
        mock.assert_called_with("q", 20)


_FETCH = "naas_abi_core.utils.outbound.fetch"
_CONNECT = "naas_abi_core.utils.outbound.httpcore.SyncBackend.connect_tcp"


def _html_response(
    body: bytes, content_type: str = "text/html; charset=utf-8"
) -> FetchedResponse:
    return FetchedResponse(
        url="https://example.com/",
        status_code=200,
        headers={"content-type": content_type},
        content=body,
        truncated=False,
    )


def test_web_fetch_rejects_non_http_and_strips_html() -> None:
    tool = make_web_fetch_tool()
    assert tool.name == "web_fetch"
    assert "Error" in tool.invoke({"url": "ftp://example.com/file"})

    resp = _html_response(b"<html><body><p>Hello world</p></body></html>")
    with patch(_FETCH, return_value=resp):
        result = tool.invoke({"url": "https://example.com"})
    assert "Hello world" in result
    assert "<p>" not in result


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "file://localhost/etc/shadow",
        "ftp://internal.example.com/secrets",
        "data:text/plain;base64,aGVsbG8=",
        "gopher://example.com/",
        "jar:file:///etc/passwd!/",
    ],
)
def test_web_fetch_refuses_every_scheme_but_http_and_https(url: str) -> None:
    """The URL is model output, so the scheme is attacker-reachable.

    web_fetch is bound into every agent, and its argument comes from whatever
    the model decided to read: a link off a search result, a URL quoted in a
    page it just fetched, or an instruction planted in either. `file:///etc/passwd`
    must never be read out into the transcript, so only http and https are
    spoken, before any connection opens.
    """
    tool = make_web_fetch_tool()

    with patch(_CONNECT) as connect:
        result = tool.invoke({"url": url})

    assert "Error" in result
    assert "http" in result
    connect.assert_not_called()


def test_web_fetch_accepts_an_uppercase_scheme() -> None:
    """Scheme comparison is case-insensitive per RFC 3986, unlike startswith."""
    resp = _html_response(b"<p>ok</p>")
    with patch(_FETCH, return_value=resp):
        assert "ok" in make_web_fetch_tool().invoke({"url": "HTTPS://example.com"})


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[fd00:ec2::254]/latest/meta-data/",
        "http://127.0.0.1:10217/api/v1/agents",
        "http://localhost:12334/",
        "http://api.localhost/",
        "http://10.0.0.7/admin",
        "http://192.168.1.1/",
        "http://[::1]:8080/",
        "http://forgejo.local/",
    ],
)
def test_web_fetch_refuses_metadata_and_private_hosts(url: str) -> None:
    """An http:// URL is a valid scheme pointing at the wrong network.

    Everything web_fetch reads is returned into the transcript, so an instance
    metadata endpoint is a credential read with an audience. The private and
    loopback ranges are the same shape one hop down: the live API and Nexus are
    on loopback ports on the machine running the agent.

    Addresses and local names written in the URL are refused before any
    connection opens; names that resolve to such addresses are covered in
    web_fetch_public_test.py.
    """
    tool = make_web_fetch_tool()

    with patch(_CONNECT) as connect:
        result = tool.invoke({"url": url})

    assert "Error" in result
    connect.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "https://naas.ai/pricing?plan=team#faq",
        "https://8.8.8.8/",
        "https://docs.naas.ai:8443/",
    ],
)
def test_web_fetch_still_opens_ordinary_public_urls(url: str) -> None:
    """The deny list must not cost the tool its actual job.

    Query strings and fragments are in here on purpose: the endpoint validator
    in the Nexus API rejects both, which is correct for a provider base URL and
    would break fetching most pages on the web.
    """
    resp = _html_response(b"<p>public</p>")
    with patch(_FETCH, return_value=resp):
        assert "public" in make_web_fetch_tool().invoke({"url": url})


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
    with patch("naas_abi.tools.web_tools._ddgs_search", return_value=[]) as mock:
        tool.invoke({"query": "q", "max_results": 0})
    mock.assert_called_once_with("q", 1)


def test_web_search_truncates_snippets_and_tolerates_other_key_names() -> None:
    tool = make_web_search_tool()
    long_body = [{"title": "T", "href": "https://example.com", "body": "X" * 500}]
    with patch("naas_abi.tools.web_tools._ddgs_search", return_value=long_body):
        assert "X" * 251 not in tool.invoke({"query": "q"})

    reset_web_tool_turn()
    short_keys = [{"t": "Title", "u": "https://x.com", "d": "Desc"}]
    with patch("naas_abi.tools.web_tools._ddgs_search", return_value=short_keys):
        assert "Title" in tool.invoke({"query": "q"})


def test_web_fetch_marks_truncated_pages() -> None:
    tool = make_web_fetch_tool()
    resp = _html_response(b"A" * 10_000, content_type="text/plain")

    with patch(_FETCH, return_value=resp):
        result = tool.invoke({"url": "https://x.com", "max_length": 100})

    assert "truncated" in result
    assert len(result) <= 200


def test_web_fetch_rejects_the_same_url_twice() -> None:
    tool = make_web_fetch_tool()
    resp = _html_response(b"<p>ok</p>")
    with patch(_FETCH, return_value=resp):
        assert "ok" in tool.invoke(
            {"url": "https://www.forvismazars.com/il/en/offices"}
        )
        blocked = tool.invoke({"url": "https://www.forvismazars.com/il/en/offices"})
    assert "already ran" in blocked
    assert "Stop and reply" in blocked


def test_web_fetch_rejects_truncated_oss_url_then_repeat() -> None:
    tool = make_web_fetch_tool()
    url = (
        "https://routify-file-proxy-sg.oss-ap-southeast-1.aliyuncs.com/x"
        "?OSSAccessKeyId=LTAI5t…QVZr"
    )
    with patch(_FETCH) as fetch:
        first = tool.invoke({"url": url})
        second = tool.invoke({"url": url})
    assert "truncated" in first.lower() or "ellipsis" in first.lower()
    assert "already ran" in second
    fetch.assert_not_called()


def test_web_search_drops_truncated_result_urls() -> None:
    tool = make_web_search_tool()
    fake = [
        {
            "title": "Good",
            "href": "https://www.forvismazars.com/il/en/offices",
            "body": "ok",
        },
        {
            "title": "Bad",
            "href": "https://routify.example/x?id=LTAI5t…QVZr",
            "body": "junk",
        },
    ]
    with patch("naas_abi.tools.web_tools._ddgs_search", return_value=fake):
        result = tool.invoke({"query": "Forvis Mazars Israel 2026"})
    assert "forvismazars.com" in result
    assert "routify" not in result
    again = tool.invoke({"query": "Forvis Mazars Israel 2026"})
    assert "already ran" in again


def test_web_fetch_reports_transport_failures_as_text() -> None:
    """Returned, not raised: the caller is a model reading a tool result."""
    from naas_abi_core.utils.outbound import OutboundError

    tool = make_web_fetch_tool()
    missing = FetchedResponse(
        url="https://x.com/missing",
        status_code=404,
        headers={"content-type": "text/html"},
        content=b"Not Found",
        truncated=False,
    )
    with patch(_FETCH, return_value=missing):
        assert "404" in tool.invoke({"url": "https://x.com/missing"})

    with patch(_FETCH, side_effect=OutboundError("the host could not be reached")):
        assert "Could not reach" in tool.invoke({"url": "https://nonexistent.invalid"})
