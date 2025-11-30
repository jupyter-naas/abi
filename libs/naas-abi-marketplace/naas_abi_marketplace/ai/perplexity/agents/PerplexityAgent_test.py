import pytest


@pytest.fixture
def agent():
    from naas_abi.core.perplexity.agents.PerplexityAgent import create_agent

    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    # Perplexity: My name is Perplexity. How can I assist you today?

    assert result is not None, result
    assert "Perplexity" in result, result


def test_search_news_with_datetime(agent):
    from datetime import datetime

    result = agent.invoke(
        "What are the news of the day? Start by: 'As of today the date is YYYY-MM-DD.'"
    )

    # Perplexity: As of today the date is 2025-09-25.

    # Here are some of the top news stories of the day:

    #  • A deadly shooting occurred at an ICE facility in Dallas, resulting in at least one detainee's death.
    #  • President Trump is expected to sign a deal to facilitate the sale of TikTok to an American buyer.
    #  • Trump is also preparing to host Turkish President Erdogan for talks at the White House.
    #  • NASA has accelerated the Artemis II mission timeline, now aiming for a February 2026 launch to fly astronauts around the moon.
    #  • The Gaza conflict continues, with Israeli attacks killing at least 72 Palestinians amid efforts to capture Gaza City.
    #  • Russia has expanded its drone attacks into Polish airspace, prompting Poland to shoot down drones and invoke NATO's Article 4 for consultations.
    #  • Canada has signed a significant trade deal with Indonesia and a new defense pact.
    #  • A search is ongoing for a missing 5-year-old boy in Alberta, Canada.
    #  • Planned Parenthood of Wisconsin will halt abortion services starting October 1 due to Medicaid funding cuts.
    #  • There is an overdose spike alert in Addison County linked to suspected fentanyl in street drugs.
    #  • Comedian Jimmy Kimmel has returned to airwaves with a strong defense of free speech.
    #  • Super Typhoon Ragasa has made landfall in southern China, causing severe damage and tsunami-like waves in Taiwan.

    # Other notable news includes a stabbing incident at a Pittsburgh high school injuring three students, and a driver charged in a pregnant woman's hit-and-run death in Illinois.

    # Sources:

    #  • NBC News YouTube - Sept 25 Headlines
    #  • Global News Morning Headlines Sept 25
    #  • Wikipedia Current Events Sept 2025
    #  • News 3 Now This Morning Sept 25
    #  • ABC News Latest
    #  • The Independent News Sept 24

    assert result is not None, result
    assert datetime.now().strftime("%Y-%m-%d") in result, result
    assert "sources" in result.lower(), result


def test_search_news_intent(agent):
    result = agent.invoke("search news about artificial intelligence")

    # Perplexity: Here are the latest news highlights about artificial intelligence as of late September 2025:

    #  • OpenAI, Oracle, and SoftBank have announced five new U.S. AI data center sites, aiming for about 10 GW of AI compute capacity and investments exceeding $400 billion. This expansion supports the growing demand for
    #    AI infrastructure.
    #  • Microsoft is integrating Anthropic’s Claude models into Microsoft 365 Copilot and Copilot Studio, giving enterprises more AI model choices for research and agent building.
    #  • Meta is extending access to its Llama AI model to U.S. allies in Europe and Asia, including NATO and EU institutions, broadening government and defense AI use cases.
    #  • Apple is developing a new system called World Knowledge Answers to significantly upgrade Siri’s intelligence, aiming to compete with OpenAI and Google in AI-powered search.
    #  • The U.S. government, under the Trump administration, recently hosted tech leaders to emphasize maintaining American leadership in AI, highlighting its importance as a national priority.
    #  • A $3 billion AI-focused data center is planned in Harwood, North Dakota, reflecting the massive computational needs of modern AI systems.
    #  • MIT is advancing AI research in clinical applications, workplace tools, automated theorem proving, and scientific predictions, and recently hosted a symposium on generative AI’s impact.
    #  • The United Nations has established two new bodies to promote inclusive international AI governance and provide evidence-based policy guidance.
    #  • Recent AI research is focusing on multimodal reasoning, explainability, robustness, security, and automation of complex workflows, with applications in healthcare, logistics, and security.
    #  • UN leaders and experts are calling for more inclusive AI development, investment in smaller adaptive systems, and ensuring linguistic and cultural diversity in AI models to avoid concentration of benefits.

    # Sources:

    #  • True Future Media
    #  • Rapid Assure
    #  • MIT News
    #  • UN News
    #  • UN News - AI Governance

    assert result is not None, result
    assert "artificial intelligence" in result.lower(), result
    assert "sources" in result.lower(), result
