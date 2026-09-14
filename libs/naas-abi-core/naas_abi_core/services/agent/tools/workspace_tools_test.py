from naas_abi_core.services.agent.tools.workspace_tools import (
    _MAX_READ_CHARS,
    _sanitize_workspace_read,
)


def test_sanitize_workspace_read_leaves_small_text_alone() -> None:
    raw = {"ok": True, "path": "README.md", "content": "# hi"}
    assert _sanitize_workspace_read("README.md", raw) is raw


def test_sanitize_workspace_read_redacts_data_urls_on_deck() -> None:
    html = (
        '<html><img src="data:image/png;base64,AAAA"></html>'
    )
    out = _sanitize_workspace_read(
        "slides/ws-1/untitled-x/deck.html",
        {"ok": True, "content": html},
    )
    assert "AAAA" not in out["content"]
    assert "[REDACTED_DATA_URL]" in out["content"]
    assert "transfer_to_Slides" in out["warning"]
    assert "Redacted 1 embedded data-URLs." in out["warning"]


def test_sanitize_workspace_read_omits_document_html() -> None:
    html = "<html><body><h1>Portrait A4</h1>" + ("x" * 200) + "</body></html>"
    out = _sanitize_workspace_read(
        "documents/ws-1/untitled-x/document.html",
        {"ok": True, "content": html},
    )
    assert out["content"] == ""
    assert out["html_omitted"] is True
    assert "apply_documents_template" in out["warning"]
    assert "Portrait A4" not in out["content"]


def test_sanitize_workspace_read_truncates_huge_text() -> None:
    content = "x" * (_MAX_READ_CHARS + 50)
    out = _sanitize_workspace_read("notes.txt", {"ok": True, "content": content})
    assert out["content"].endswith("...[truncated]...")
    assert len(out["content"]) < len(content)
    assert "Truncated" in out["warning"]
