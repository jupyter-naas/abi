import pytest
from naas_abi_marketplace.applications.powerpoint.agents.PowerPointAgent import (
    create_agent,
)


@pytest.fixture
def agent():
    return create_agent()


def test_powerpoint_agent(agent):
    result = agent.invoke("Create presentation about ontology")

    assert result is not None, "Result is None"
    assert "slides" in result, f"Slides are not in result: {result}"
    assert "target" or "audience" or "objective" in result, (
        f"Target, audience or objective are not in result: {result}"
    )

    slide_number = 3
    result = agent.invoke(
        f"{str(slide_number)} slides, general audience, objective: to explain what is ontology"
    )

    assert result is not None, "Result is None"
    for i in range(slide_number):
        assert f"Slide {i}" in result, f"Slide {i} is not in result: {result}"

    # Validate slide structure
    result = agent.invoke("Go")

    assert result is not None, "Result is None"
    for i in range(slide_number):
        assert f"### Slide {i}" in result, f"Slide {i} is not in result: {result}"
        assert "Sources" in result, f"Sources are not in result: {result}"
        assert "TemplateSlideUri" in result, (
            f"TemplateSlideUri is not in result: {result}"
        )

    # Validate slide content
    result = agent.invoke("Go")

    assert result is not None, "Result is None"
    assert "Your presentation has been successfully created" in result, (
        f"Text creation not in result: {result}"
    )
    assert "api.naas.ai" in result, f"api.naas.ai is not in result: {result}"
