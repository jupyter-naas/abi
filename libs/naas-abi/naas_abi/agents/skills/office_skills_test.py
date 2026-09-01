from naas_abi.agents.skills.office_skills import (
    list_office_skill_records,
    load_office_skill,
    office_skill_tools,
)


def test_slides_office_skill_is_registered() -> None:
    names = {name for name, _fm, _path in list_office_skill_records()}
    assert "slides" in names
    assert "docs" not in names
    assert "sheets" not in names


def test_slides_skill_requires_research_and_html_source() -> None:
    text = load_office_skill("slides")
    assert "web_search" in text
    assert "deck.html" in text
    assert "SlidesAgent" in text
    assert "start writing immediately" not in text
    assert "Context / Approach / Plan" in text


def test_office_skill_tools_list_and_read() -> None:
    list_tool, read_tool = office_skill_tools()
    listed = list_tool.invoke({})
    assert "slides" in listed.lower()
    body = read_tool.invoke({"name": "slides"})
    assert "web_search" in body
    missing = read_tool.invoke({"name": "docs"})
    assert "Unknown" in missing
