import pytest
from naas_abi_marketplace.applications.sanax.agents.SanaxAgent import create_agent


@pytest.fixture
def agent():
    pytest.main(
        [
            "src/marketplace/applications/sanax/pipelines/SanaxLinkedInSalesNavigatorExtractorPipeline_test.py"
        ]
    )
    return create_agent()


def test_get_all_people(agent):
    response = agent.invoke("List all people in the database")
    assert "Emma Wilson" in response
    assert "David Kim" in response
    assert "Maria Garcia" in response
    assert "Jane Doe" in response
    assert "Sarah Johnson" in response
    assert "Michael Chang" in response
    assert "Lisa Chen" in response
    assert "John Wilson" in response
    assert "Thomas Mueller" in response
    assert "John Smith" in response


def test_get_person_location(agent):
    response = agent.invoke("Where is Emma Wilson located?")
    assert "Berlin, Germany" in response

    response = agent.invoke("What is David Kim's location?")
    assert "South Korea" in response


def test_get_person_company(agent):
    response = agent.invoke("Where does Maria Garcia work?")
    assert "Global Ventures" in response
    assert "Business Development Manager" in response

    response = agent.invoke("Who works at Tech Solutions?")
    assert "Jane Doe" in response


def test_get_person_role(agent):
    response = agent.invoke("What is Emma Wilson's role?")
    assert "Product Manager" in response
    assert "Digital Solutions" in response

    response = agent.invoke("What is David Kim's position?")
    assert "Solutions Architect" in response
    assert "Cloud Systems" in response


def test_get_person_details(agent):
    response = agent.invoke("Tell me about Maria Garcia")
    assert "Global Ventures" in response
    assert "Business Development Manager" in response

    response = agent.invoke("What do you know about Emma Wilson?")
    assert "Product Manager" in response
    assert "Digital Solutions" in response
    assert "Berlin, Germany" in response
