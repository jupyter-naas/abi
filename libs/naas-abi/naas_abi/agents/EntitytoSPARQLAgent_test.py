import pytest
from naas_abi.agents.EntitytoSPARQLAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_basic_functionality_and_output_structure(agent):
    """
    Test 1: Basic Functionality and Output Structure

    Verifies that the agent returns a response containing:
    1. Original text acknowledgment
    2. Entity extraction explanation with BFO reasoning
    3. Relationship analysis and justification
    4. Complete SPARQL INSERT DATA statement
    """
    from datetime import datetime

    statement = """latest news on France today:
    Major Wildfire in Southern France (Aude Region)
    A devastating wildfire—France's largest in decades—has been brought under control after sweeping through over 16,000 hectares (160 km²), an area larger than Paris 
    Reuters
    France 24
    AP News
    """

    result = agent.invoke(statement)
    result_str = str(result)

    # Test that result is not empty
    assert result_str is not None and result_str.strip() != "", (
        "Agent should return non-empty result"
    )

    # Test for original text acknowledgment
    assert "Entity Extraction Analysis" in result_str, (
        "Should contain Entity Extraction Analysis section"
    )
    assert "original text" in result_str.lower(), "Should acknowledge original text"

    # Test for entity extraction explanation
    assert "Extracted Entities" in result_str, (
        "Should contain Extracted Entities section"
    )
    assert "BFO" in result_str, "Should reference BFO ontology framework"
    assert "Continuants" in result_str or "Occurrents" in result_str, (
        "Should categorize entities as Continuants or Occurrents"
    )

    # Test for relationship analysis
    assert "Relationships" in result_str, "Should contain relationship analysis"
    assert "Justification" in result_str or "Reasoning" in result_str, (
        "Should provide justification for relationships"
    )

    # Test for SPARQL statement
    assert "```sparql" in result_str, "Should contain SPARQL statement"
    assert "INSERT DATA" in result_str, "Should contain INSERT DATA clause"

    # Test date
    assert datetime.now().strftime("%Y-%m-%d") in result_str, (
        "Should contain today's date"
    )
