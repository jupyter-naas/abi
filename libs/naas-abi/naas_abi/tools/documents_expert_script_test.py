"""Expert User Script against the shared HTML mutators (HTTP, CLI, agent)."""

from __future__ import annotations

from naas_abi.tools.documents_commands import (
    PAGE_BREAK_HTML,
    apply_document_commands,
    heading_outline,
    update_document_title,
)

TITLE = "Website Redesign Proposal"
SECTIONS = ("Overview", "Objectives", "Scope", "Timeline", "Next Steps")
LINK = "https://www.forvismazars.com"
IMAGE = "https://example.com/hero.png"


def _blank_seed(title: str = "Untitled document") -> str:
    return (
        "<!doctype html><html><head>"
        f"<title>{title}</title></head><body><main class=\"document\">"
        '<section class="page flow"><div class="doc-body">'
        f'<h1 class="fmz-title" data-slot="title">{title}</h1>'
        "</div></section></main></body></html>"
    )


def _script_requests() -> list[dict]:
    requests: list[dict] = [{"type": "rename_document", "title": TITLE}]
    bodies = {
        "Overview": "We will refresh the public website.",
        "Objectives": "Ship a faster, clearer site.",
        "Scope": "Marketing pages and the client portal.",
        "Timeline": "The launch is in June.",
        "Next Steps": "Approve the budget this week.",
    }
    for name in SECTIONS:
        requests.append(
            {"type": "insert_heading", "title": name, "level": 2, "after_heading": -1}
        )
        requests.append(
            {
                "type": "insert_paragraph",
                "text": bodies[name],
                "after_heading": -1,
            }
        )
    requests.extend(
        [
            {"type": "apply_mark", "find": "refresh", "mark": "strong"},
            {
                "type": "insert_list",
                "items": ["Discovery", "Build", "Launch"],
                "after_heading": 2,
            },
            {
                "type": "insert_list",
                "items": ["Week 1", "Week 2", "Week 3"],
                "ordered": True,
                "after_heading": 4,
            },
            {
                "type": "insert_table",
                "headers": ["Phase", "Owner", "Due Date"],
                "rows": [
                    ["Discover", "Alex", "3 Oct"],
                    ["Build", "Sam", "31 Oct"],
                    ["Launch", "Jordan", "21 Nov"],
                ],
                "after_heading": 4,
            },
            {"type": "insert_link", "find": "public website", "href": LINK},
            {
                "type": "insert_image",
                "src": IMAGE,
                "alt": "Hero",
                "after_heading": 1,
            },
            {
                "type": "replace_text",
                "find": "Approve the budget this week.",
                "replace": "Approve scope and budget this week.",
            },
            {"type": "insert_page_break", "after_heading": 3},
            {
                "type": "insert_comment",
                "find": "client portal",
                "comment": "Confirm portal owner.",
            },
            {"type": "insert_suggestion", "find": "June", "replace": "July"},
        ]
    )
    return requests


def test_expert_user_script_against_html() -> None:
    seed = _blank_seed()
    renamed = update_document_title(seed, TITLE)
    assert isinstance(renamed, str)
    assert TITLE in renamed

    result = apply_document_commands(seed, _script_requests())
    assert result.get("ok") is True, result
    html = result["html"]
    assert TITLE in html
    assert f"<title>{TITLE}</title>" in html

    titles = [item["title"] for item in heading_outline(html)]
    assert titles[0] == TITLE
    for name in SECTIONS:
        assert name in titles
        assert f'class="fmz-heading-1">{name}</h2>' in html

    assert "<strong>refresh</strong>" in html
    assert "<ul>" in html and "<li>Discovery</li>" in html
    assert "<ol>" in html and "<li>Week 1</li>" in html
    assert '<table class="fmz-table">' in html
    assert "<th>Phase</th>" in html
    assert "<th>Owner</th>" in html
    assert "<th>Due Date</th>" in html
    assert html.count("<tr>") >= 4
    assert f'<a href="{LINK}">public website</a>' in html
    assert f'<img src="{IMAGE}" alt="Hero" />' in html
    assert "Approve scope and budget this week." in html
    assert "Approve the budget this week." not in html
    assert PAGE_BREAK_HTML in html
    assert 'data-comment="Confirm portal owner."' in html
    assert '<del class="fmz-suggest-del">June</del>' in html
    assert '<ins class="fmz-suggest-ins">July</ins>' in html


def test_expert_script_verbs_are_known_commands() -> None:
    from naas_abi.tools.documents_commands import KNOWN_COMMANDS

    for name in (
        "apply_mark",
        "insert_link",
        "insert_image",
        "insert_comment",
        "insert_suggestion",
        "insert_page_break",
        "insert_list",
        "insert_table",
        "replace_text",
        "rename_document",
    ):
        assert name in KNOWN_COMMANDS
