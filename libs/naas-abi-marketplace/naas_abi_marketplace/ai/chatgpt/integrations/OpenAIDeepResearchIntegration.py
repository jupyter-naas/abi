from dataclasses import dataclass
from enum import Enum
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_marketplace.ai.chatgpt import ABIModule
from openai import OpenAI
from pydantic import BaseModel, Field

cache = CacheFactory.CacheFS_find_storage(subpath="openai_deep_research")


class DeepResearchModel(str, Enum):
    # Fast research, but less accurate
    o4_mini_deep_research = "o4-mini-deep-research"

    # Lenghty research, but more accurate
    o3_deep_research = "o3-deep-research"


@dataclass
class OpenAIDeepResearchIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenAIDeepResearch workflow.

    Attributes:
        openai_api_key (str): OpenAI API key for authentication
        model (DeepResearchModel): Deep research model to use for analysis
        system_prompt (str): System prompt to guide the research behavior
    """

    openai_api_key: str
    model: DeepResearchModel = DeepResearchModel.o3_deep_research
    system_prompt: str = """
You are a professional researcher preparing a structured, data-driven report in response to the user's question. Your task is to analyze the topic with a focus on actionable, evidence-based insights.

Do:

    Emphasize data-rich content: include specific figures, trends, statistics, and measurable outcomes (e.g., cost reductions, market size, adoption rates, usage metrics).
    When applicable, summarize data in a format that could be visualized (e.g., “this could be presented as a line graph showing year-over-year growth”).
    Prioritize credible, up-to-date sources: peer-reviewed publications, reputable institutions, regulatory bodies, or industry reports.
    Include inline citations and provide full source metadata.

Be analytical, avoid vague statements, and ensure each section contributes to a fact-based understanding that could inform decision-making or strategic planning.
"""


class OpenAIDeepResearchIntegration(Integration):
    """Workflow for performing web searches using OpenAI."""

    __configuration: OpenAIDeepResearchIntegrationConfiguration

    def __init__(self, configuration: OpenAIDeepResearchIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.openai_client = OpenAI(api_key=self.__configuration.openai_api_key)

    @cache(
        lambda self, query: self.__configuration.model
        + self.__configuration.system_prompt
        + query,
        cache_type=DataType.PICKLE,
    )
    def run(self, query: str) -> Any:
        """Execute the deep research workflow.

        Args:
            parameters (OpenAIDeepResearchParameters): Search parameters

        Returns:
            str: Search results from OpenAI
        """

        response = self.openai_client.responses.create(
            model="o3-deep-research",
            input=[
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self.__configuration.system_prompt,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": query,
                        }
                    ],
                },
            ],
            reasoning={"summary": "auto"},
            tools=[
                {"type": "web_search_preview"},
                {
                    "type": "code_interpreter",
                    "container": {"type": "auto", "file_ids": []},
                },
            ],
        )

        return response


def as_tools(
    configuration: OpenAIDeepResearchIntegrationConfiguration,
) -> list[BaseTool]:
    """Returns a list of LangChain tools for this workflow.

    Returns:
        list[BaseTool]: List containing the workflow tool
    """
    integration = OpenAIDeepResearchIntegration(configuration)

    class OpenAIDeepResearchParameters(BaseModel):
        query: str = Field(
            ..., description="The query to perform a deep research using OpenAI."
        )

    return [
        StructuredTool(
            name="openai_deep_research",
            description="Perform a deep research using OpenAI.",
            func=lambda query: integration.run(query),
            args_schema=OpenAIDeepResearchParameters,
        )
    ]


if __name__ == "__main__":
    module: ABIModule = ABIModule.get_instance()

    configuration = OpenAIDeepResearchIntegrationConfiguration(
        openai_api_key=module.configuration.openai_api_key,
        model=DeepResearchModel.o3_deep_research,
    )

    integration = OpenAIDeepResearchIntegration(configuration)

    query = """
# MetaPrompt: Market Intelligence Slides - Generic Template

## Company Variable
TARGET_COMPANY:  Michelin

## Usage Instructions
1. Replace {TARGET_COMPANY} with the actual company name (e.g., "Orange", "Tesla", "Nike")
2. Replace {DATE} with the presentation date in YYYY-MM-DD format
3. Generate a complete Market Intelligence presentation following Forvis Mazars standards

## Objective
Generate a comprehensive Market Intelligence presentation for {TARGET_COMPANY} following the Forvis Mazars ontology structure. This should be a professional business document suitable for client engagement and strategic discussions.

## Document Structure Requirements

### PART 1: WHAT WE OBSERVE ABOUT YOU (Slides 5-16)
Create detailed analysis sections covering:

#### Slide 5: Offerings
- Question: "What makes your products and services unique in your market?"
- Content Requirements: 
  - Analyze {TARGET_COMPANY}'s core products and service portfolio
  - Cover primary business lines and market segments
  - Highlight innovation initiatives and competitive advantages
  - Include specific product differentiators and market positioning
  - Use 6 numbered key points with detailed explanations

#### Slide 6: Capabilities 
- Question: "How do you ensure the operational excellence of your offering?"
- Content Requirements:
  - Manufacturing excellence and global production network
  - R&D capabilities and innovation pipeline
  - Supply chain management and quality control
  - Digital transformation initiatives
  - Sustainability practices in operations
  - Training and development programs

#### Slide 7: Market Dynamics
- Question: "What are the current dynamics of your market?"
- Content Requirements:
  - Global market size and growth projections for {TARGET_COMPANY}'s industry
  - Regional market performance across key geographic markets
  - Key market trends and drivers affecting the industry
  - Recent financial performance highlights
  - Include specific market data, percentages, and monetary figures
  - Cite relevant sources

#### Slide 8: Market SWOT
- Question: "What are the strengths, weaknesses, opportunities, and threats in your market?"
- Format: 2x2 grid with:
  - Strengths: Brand recognition, innovation leadership, global presence, market positioning
  - Weaknesses: Cost structure, market dependencies, operational challenges
  - Opportunities: Emerging markets, digital transformation, new technologies, sustainability initiatives
  - Threats: Competition, supply chain risks, economic volatility, regulatory changes

#### Slide 9: Competitive Positioning
- Question: "How do you position yourself in relation to your competitors?"
- Content Requirements:
  - {TARGET_COMPANY} vs. [Major Competitor 1] comparison
  - {TARGET_COMPANY} vs. [Major Competitor 2] comparison  
  - {TARGET_COMPANY} vs. [Major Competitor 3] comparison
  - Include market share, geographical presence, technology focus, financial metrics
  - Use specific data points and strategic differentiators

#### Slide 10: Differentiators
- Question: "What are your main differentiating factors compared to your competitors?"
- Content Requirements:
  - Technology and innovation leadership (specific examples)
  - Sustainability initiatives and environmental commitments
  - Digital transformation and technology adoption
  - Global operational footprint and capabilities
  - Brand heritage and market positioning
  - Key strategic programs and initiatives

#### Slide 11: Competitor Advantages
- Question: "What are your competitors doing that you are not?"
- Content Requirements:
  - [Major Competitor 1]'s specific competitive advantages
  - [Major Competitor 2]'s market strategies and innovations
  - [Major Competitor 3]'s technological focus areas
  - Other competitors' strategic moves and differentiators
  - Areas where {TARGET_COMPANY} could improve or catch up

#### Slide 12: Financial Performance
- Question: "How is your financial performance compared to your competitors?"
- Content Requirements:
  - Revenue growth and profitability metrics
- Market capitalization comparisons with industry peers
  - Regional/segment financial performance
  - Key financial ratios and industry benchmarks
  - Recent quarterly/annual results with specific figures

#### Slide 13: Strategic Directions
- Question: "Where is your current strategy heading?"
- Content Requirements:
  - Current strategic plan and long-term vision details
  - Sustainability commitments and environmental targets
  - Digital transformation roadmap
  - Market expansion and growth strategies
  - Innovation priorities and R&D focus
  - Use numbered strategic pillars (1, 2, 3)

#### Slide 14: Board Contributions
- Question: "How can the board of directors contribute to the success of the strategy?"
- Content Requirements:
  - Key leadership team profiles with names and titles for {TARGET_COMPANY}
  - CEO and executive team backgrounds and expertise
  - Board composition, expertise and strategic contributions
  - Recent leadership changes and appointments
  - Role of each leader in strategy execution and governance

#### Slide 15: Strategic Execution Challenges
- Question: "What are your biggest challenges in executing this strategy?"
- Content Requirements:
  - Supply chain and operational challenges
  - Sustainability transition costs and implementation complexity
  - Technology evolution and digital transformation hurdles
  - Market competition and competitive pressure
  - Regulatory compliance across markets and jurisdictions
  - Economic volatility, currency risks, and market uncertainties

#### Slide 16: Latest News
- Question: "What are the most recent developments or major updates within your organization?"
- Content Requirements:
  - Recent partnerships, acquisitions, and strategic alliances
  - New product/service launches and innovations
  - Sustainability initiatives and ESG achievements
  - Leadership changes, appointments, and organizational updates
  - Financial results, earnings announcements, and strategic communications
  - Include specific dates and credible sources

### PART 2: WHO WE ARE (Slides 17-33)
- Use the standard Forvis Mazars content about the firm
- Include global presence, service offerings, values, and capabilities
- Maintain consistent branding and messaging

### PART 3: WHAT WE CAN DO TOGETHER (Slides 34-41)
- Focus on collaborative engagement model
- Assessment, Strategy, Planning, Execution, Evaluation, Evolution framework
- Emphasize joint value creation and strategic partnership

## Content Guidelines

### Research Requirements
- Use current, accurate data from 2024-2025
- Include specific financial figures, market data, and performance metrics for {TARGET_COMPANY}
- Cite reputable sources (company reports, industry analyses, financial news, analyst reports)
- Focus on recent developments and strategic initiatives specific to {TARGET_COMPANY}

### Writing Style
- Professional, analytical tone suitable for C-level executives
- Clear, concise bullet points with detailed explanations
- Use specific examples and quantifiable achievements
- Balance critical analysis with positive positioning

### Data Integration
- Include market share percentages, revenue figures, growth rates
- Use comparative analysis with specific competitor metrics
- Incorporate recent financial results and forecasts
- Reference industry benchmarks and market trends

### Structure Consistency
- Follow the slide numbering and question format exactly
- Maintain the visual hierarchy and content organization
- Use consistent terminology and branding throughout
- Include date references (26 June 2025) where specified

## Output Requirements

Generate a complete markdown document titled "{DATE}_MarketIntelligenceSlides_{TARGET_COMPANY}_EN.md" that:

1. Maintains Professional Quality: Suitable for client presentation
2. Includes Comprehensive Analysis: Deep insights into {TARGET_COMPANY}'s business and market position
3. Uses Current Data: 2024-2025 information with specific metrics and KPIs
4. Follows Format Exactly: Matches the established Forvis Mazars template structure
5. Provides Actionable Insights: Strategic recommendations and business observations
6. Cites Sources: Credible references for key claims and data points

## Success Criteria

The generated document should:
- Be immediately usable in a client meeting with {TARGET_COMPANY} executives
- Demonstrate deep understanding of {TARGET_COMPANY}'s business and competitive landscape
- Provide valuable strategic insights that could inform business decisions
- Maintain Forvis Mazars' professional standards and analytical rigor
- Include sufficient detail to support meaningful strategic discussions
- Be industry-specific and tailored to {TARGET_COMPANY}'s market context

---

Instructions for LLM: Use this meta-prompt to create a comprehensive, professional Market Intelligence presentation for {TARGET_COMPANY} that matches the quality and depth of analysis expected from a top-tier consulting firm. Research current information about {TARGET_COMPANY} and their industry to populate all sections with accurate, relevant, and strategic content."""
    response = integration.run(query)
    import rich

    rich.inspect(response)
    rich.print(f"Output text: {response.output_text}")
