from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from src.core.modules.common.integrations.PerplexityIntegration import (
    PerplexityIntegration,
    PerplexityIntegrationConfiguration,
)
from abi import logger
from pydantic import Field, BaseModel
from typing import Optional, List, Dict, Tuple
import os
from datetime import datetime
import json
from src.services import services
from lib.abi.services.object_storage.ObjectStoragePort import (
    Exceptions as ObjectStorageExceptions,
)
from abi.utils.JSON import extract_json_from_completion
from abi.utils.String import create_id_from_string


@dataclass
class PerplexityOrganizationWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for OrganizationAnalysis workflow.

    Attributes:
        perplexity_integration_config (PerplexityIntegrationConfiguration): Configuration for Perplexity integration
    """

    perplexity_integration_config: PerplexityIntegrationConfiguration
    data_store_path: str = "datalake/opendata/organizations"


class PerplexityOrganizationParameters(WorkflowParameters):
    """Parameters for OrganizationAnalysis workflow execution.

    Attributes:
        organization_name (str): Name of the organization to analyze
        website (str): Website URL of the organization
        data_store_name (str): Data store name to store the data
    """

    organization_name: str = Field(description="Name of the organization to analyze")
    metadata: Optional[Dict] = Field(
        description="Metadata of the organization. A dictionary with the following keys: `website`"
    )
    use_cache: Optional[bool] = Field(True, description="Use cache to store the data")


class PerplexityOrganizationWorkflows(Workflow):
    """Workflow for extracting data from Perplexity."""

    __configuration: PerplexityOrganizationWorkflowsConfiguration

    def __init__(self, configuration: PerplexityOrganizationWorkflowsConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__perplexity = PerplexityIntegration(
            self.__configuration.perplexity_integration_config
        )

    def init_storage(self, organization_name: str) -> Tuple[str, str]:
        organization_id = create_id_from_string(organization_name)
        return os.path.join(
            self.__configuration.data_store_path, f"{organization_id}"
        ), organization_id

    def extract_data_from_perplexity(
        self,
        organization_name: str,
        metadata: Dict,
        add_source: bool = False,
        use_cache: bool = True,
        topic_name: str = "general",
        answer_format: BaseModel = None,
        model: str = "sonar",
        temperature: float = 0,
        search_domain_filter: List[str] = ["perplexity.ai"],
    ) -> Dict:
        """Extract data from Perplexity."""
        # Initialize storage
        output_dir, organization_id = self.init_storage(organization_name)

        # Create filenames
        topic_id = create_id_from_string(topic_name)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"perplexity_{organization_id}_{topic_id}.json"
        filename_copy = f"{timestamp}_perplexity_{organization_id}_{topic_id}.json"

        try:
            completion = services.storage_service.get_object(
                output_dir, filename
            ).decode("utf-8")
            data = json.loads(completion)
        except ObjectStorageExceptions.ObjectNotFound:
            completion = None
            data = None

        if completion is None or use_cache is False:
            logger.info(
                f"Extracting data from Perplexity for {organization_name} - {topic_name}"
            )
            source_details = ""
            if add_source:
                source_details = ", `source`: The name of the source used for this information, `source_url`: The URL of the source used for this information, `source_date`: The date of the source used for this information."

            # Create prompt
            prompt = f"""Analyze the organization: '{organization_name}' ({", ".join([f"{k}: {v}" for k, v in metadata.items()])}). Please output a JSON object containing the following fields: {", ".join([f'"{field}": {answer_format.model_fields[field].description}{source_details}' for field in answer_format.model_fields.keys()])}"""

            # Create system prompt
            system_prompt = """You are an experimented OSINT investigator. 
            Your goal is to extract information about a given organization.
            Rules: 
            1. Provide only the final answer in JSON format as follow: ```json <JSON>```
            2. Do not show the intermediate steps information.
            3. Be precise and exhaustive.
            4. Do not include any information that is not related to the question.
            5. Verify the information you provide is correct and accurate.
            """

            # Create response format
            response_format = {
                "type": "json_schema",
                "json_schema": {"schema": answer_format.model_json_schema()},
            }

            # Add metadata website to search domain filter if it is provided
            if metadata.get("website"):
                try:
                    website = metadata["website"]
                    # Handle URLs with or without www.
                    domain = website.replace("https://", "").replace("http://", "")
                    if domain.startswith("www."):
                        domain = domain.split("www.")[1]
                    domain = domain.split("/")[0]
                    search_domain_filter.append(domain)
                except Exception as e:
                    logger.warning(
                        f"Could not parse website domain from metadata: {str(e)}"
                    )

            try:
                response = self.__perplexity.ask_question(
                    prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    response_format=response_format,
                    model=model,
                    search_domain_filter=search_domain_filter,
                )
            except Exception as e:
                raise Exception(
                    f"Failed to extract data from Perplexity for {organization_name} - {topic_name}: {str(e)}"
                )

            # Create data to be saved
            data = {
                "organization_id": organization_id,
                "organization_name": organization_name,
                "output_dir": str(output_dir),
                "metadata": metadata,
                "topic_id": topic_name,
                "topic_name": topic_name,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "model": model,
                "temperature": temperature,
                "date_extracted": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "response_format": response_format,
                "response": response,
                "response_json": extract_json_from_completion(response),
            }

            # Save data to storage
            services.storage_service.put_object(
                prefix=output_dir,
                key=filename,
                content=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"),
            )

            # Copy data to storage
            services.storage_service.put_object(
                prefix=output_dir,
                key=filename_copy,
                content=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"),
            )
        return data

    def get_organization_general_information(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            name: str = Field(
                description="A Designative Name that is an official name for a particular entity. Return `name`: (str) name of the organization."
            )  # Proper Name (ont00001014)
            legal_name: str = Field(
                description="A Proper Name that is an official name for the designated entity as determined by a Government or court of law. Return `legal_name`: (str) legal name of the organization."
            )  # Legal Name (ont00001331)
            organization_type: str = Field(
                description="Represents the type of organization. Return value from list: commercial_organization, civil_organization, educational_organization, government_organization."
            )
            website: str = Field(
                description="Website URL of the organization. Return `website`: (str) website URL of the organization."
            )
            mission: str = Field(
                description="Describes the core purpose and primary objectives of an organization, explaining what it does, whom it serves, and how it serves them. Return `mission`: (str) mission of the organization."
            )
            vision: str = Field(
                description="Outlines the long-term aspirations or desired future state of an organization. It serves as a guiding star for strategic planning and decision-making. Return `vision`: (str) vision of the organization."
            )
            created_year: int = Field(
                description="Year when organization was created. Return `created_year`: (int) year when organization was created."
            )
            headquarters: List[Dict[str, str]] = Field(
                description="Global and regional headquarters locations. Return `type`: (str) either 'global_headquarters' or 'regional_headquarters', `country`: (str) country name, `state`: (str) state name, `city`: (str) city name, and `address`: (str) address."
            )
            number_of_employees: List[Dict[str, str]] = Field(
                description="Number of employees working in the organization. Return `value`: (int) number of employees in the organization, `year`: (int) year when the number of employees was last updated."
            )
            industries: List[Dict[str, str]] = Field(
                description="A Group of Organizations that share common characteristics, activities, or business objectives. Return list of industries where the organization operates with `name`: (str) name of the industry, `definition`: (str) definition of the industry."
            )
            ticker_symbol: str = Field(
                description="A stock symbol (or ticker symbol) is a unique series of letters assigned to a security for trading purposes. Return `ticker_symbol`: (str) ticker symbol of the organization (e.g. AAPL, TSLA, etc)."
            )
            stock_market: str = Field(
                description="Stock market where the organization's stock is traded. Return `stock_market`: (str) stock market name where the organization's stock is traded (NYSE, NASDAQ, etc)."
            )

        return self.extract_data_from_perplexity(
            organization_name=parameters.organization_name,
            metadata=parameters.metadata,
            use_cache=parameters.use_cache,
            answer_format=AnswerFormat,
            topic_name="general",
            model="sonar-pro",
            temperature=0,
            add_source=False,
        )

    def get_organization_members(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            founders: List[Dict[str, str]] = Field(
                description="Individuals who have established or founded an organization, typically recognized for their role in the creation and initial development of that organization. Return list of founders with `name`: (str) name of the founder, `role`: (str) role of the founder"
            )
            chairmans: List[Dict[str, str]] = Field(
                description="Chairman is the highest-ranking executive in a company, responsible for overseeing the company's operations and making strategic decisions. Return list of persons with `name`: (str) name of the chairman, `role`: (str) role of the chairman"
            )
            president: str = Field(
                description="President is the second-highest-ranking executive in a company, responsible for overseeing the company's operations and making strategic decisions. Return `name` and `start_date`"
            )
            vice_presidents: List[Dict[str, str]] = Field(
                description="Vice President is the third-highest-ranking executive in a company, responsible for overseeing the company's operations and making strategic decisions. Return `name`, `role` and `start_date`"
            )
            ceo: str = Field(
                description="Chief Executive Officer (CEO) is the highest-ranking executive in a company, responsible for overseeing the company's operations and making strategic decisions. Return `name` and `start_date`"
            )
            cfo: str = Field(
                description="Chief Financial Officer (CFO) is the highest-ranking financial executive in a company, responsible for overseeing the company's financial operations and making strategic decisions. Return `name` and `start_date`"
            )
            cto: str = Field(
                description="Chief Technology Officer (CTO) is the highest-ranking technology executive in a company, responsible for overseeing the company's technology operations and making strategic decisions. Return `name` and `start_date`"
            )

        return self.extract_data_from_perplexity(
            organization_name=parameters.organization_name,
            metadata=parameters.metadata,
            use_cache=parameters.use_cache,
            answer_format=AnswerFormat,
            topic_name="members",
            model="sonar-pro",
            temperature=0,
            add_source=True,
        )

    def get_organization_offerings(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            products: List[Dict[str, str]] = Field(
                description="Tangible items that are created, manufactured, or sourced to satisfy a want or need by the organization. Return list of products with `name` (str) and`description` (str)."
            )
            services: List[Dict[str, str]] = Field(
                description="Intangible activities or benefits provided by one party to another, often to solve a problem or meet a need by the organization. Return list of services with `name` (str) and `description` (str)."
            )
            markets: List[Dict[str, List[str]]] = Field(
                description="Represents the organization's economic space where buyers and sellers interact to exchange goods, services, or information, typically characterized by supply and demand dynamics. Return list of markets with `name` (str), `definition` (str), `products`: (list of str) Organization listed products in the market, `services`: (list of str) Organization listed services in the market."
            )
            market_segments: List[Dict[str, List[str]]] = Field(
                description="Represents a subset of a market, defined by specific characteristics or criteria that distinguish it from other segments, often based on consumer needs, preferences, or demographics. Return list of market segments with `name` (str), `definition` (str), `market`: (str) name of the market where the segment is, `products`: (list of str) Organization listed products in the market segment, `services`: (list of str) Organization listed services in the market segment."
            )
            positionings: List[Dict[str, List[str]]] = Field(
                description="Role that represents the strategic position and differentiation strategy of the organization within its market, highlighting how the organization distinguishes itself from competitors and is perceived by its target audience. Return list of positionings with `name` (str), `definition` (str), `market`: (list) name of the market where the positioning is, `products`: (list of str) Organization listed products in the positioning, `services`: (list of str) Organization listed services in the positioning."
            )

        return self.extract_data_from_perplexity(
            organization_name=parameters.organization_name,
            metadata=parameters.metadata,
            use_cache=parameters.use_cache,
            answer_format=AnswerFormat,
            topic_name="offerings",
            model="sonar",
            temperature=0,
            add_source=False,
        )

    def get_organization_capabilities(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            technological_capabilities: List[Dict[str, str]] = Field(
                description="Abilities and functionalities possessed by machines, software, or systems. Return `name`: (str) name of the capability, `description`: (str) description of the capability, `explanation`: (str) explanation of the capability, `source`: (str) name of the source where you found this information, `source_url`: (str) url of the source where you found this information."
            )
            human_capabilities: List[Dict[str, str]] = Field(
                description="Skills, knowledge, and abilities possessed by human beings. Return `name`: (str) name of the capability, `description`: (str) description of the capability, `explanation`: (str) explanation of the capability, `source`: (str) name of the source where you found this information, `source_url`: (str) url of the source where you found this information."
            )

        return self.extract_data_from_perplexity(
            organization_name=parameters.organization_name,
            metadata=parameters.metadata,
            use_cache=parameters.use_cache,
            answer_format=AnswerFormat,
            topic_name="capabilities",
            model="sonar",
            temperature=0,
            add_source=True,
        )

    def get_organization_corporate_structure(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            mergers: List[Dict[str, str]] = Field(
                description="An Act of Association in which two or more independent organizations unite to form a single entity, typically to enhance operational efficiency, market reach, or competitive advantage. Return `name`: (str) name of the organization's merger, `description`: (str) description of the merger terms, `year`: (str) year of the merger, `organizations`: (list of str) list of organizations involved in the merger."
            )
            acquisitions: List[Dict[str, str]] = Field(
                description="An Act of Possession in which one organization gains control over another organization, acquiring its assets, operations, and management to expand its operations or market share. Return `name`: (str) name of the organization's acquisition, `description`: (str) description of the acquisition terms, `year`: (str) year of the acquisition, `organizations`: (list of str) list of organizations involved in the acquisition."
            )
            subsidiaries: List[Dict[str, str]] = Field(
                description="An Act of Association in which an organization creates and establishes a new legal entity, known as a subsidiary, over which it retains significant control and ownership. Return `name`: (str) name of the subsidiary (organization), `legal_name`: (str) legal name of the subsidiary, `mission`: (str) mission of the subsidiary, `year`: (str) year of the establishment of the subsidiary."
            )

        return self.extract_data_from_perplexity(
            organization_name=parameters.organization_name,
            metadata=parameters.metadata,
            use_cache=parameters.use_cache,
            answer_format=AnswerFormat,
            topic_name="corporate_structure",
            model="sonar",
            temperature=0,
            add_source=True,
        )

    def get_organization_strategic_alliances(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            partnerships: List[Dict[str, str]] = Field(
                description="Planned act in which two or more organizations or individuals enter into an agreement to cooperate for mutual benefit, typically to achieve shared objectives. Return `name`: (str) name of the partnership (organization), `description`: (str) description of the partnership, `year`: (str) year of the partnership, `organizations`: (list of str) list of organizations involved in the partnership"
            )
            joint_ventures: List[Dict[str, str]] = Field(
                description="Planned act in which two or more organizations come together to undertake a specific project or business activity, sharing resources, risks, and rewards, while maintaining their distinct legal identities. Return `name`: (str) name of the organization, `description`: (str) description of the joint venture terms, `year`: (str) year of the joint venture, `organizations`: (list of str) list of organizations involved in the joint venture."
            )
            marketing_alliances: List[Dict[str, str]] = Field(
                description="Planned act in which two or more organizations enter into a cooperative relationship to promote and distribute products or services to a common audience. Return `name`: (str) name of the marketing alliance (organization), `description`: (str) description of the marketing alliance, `year`: (str) year of the marketing alliance, `organizations`: (list of str) list of organizations involved in the marketing alliance."
            )
            research_collaborations: List[Dict[str, str]] = Field(
                description="Planned act in which two or more organizations enter into a cooperative relationship to conduct research or development projects, sharing resources, expertise, and results. Return `name`: (str) name of the research collaboration (organization), `description`: (str) description of the research collaboration, `year`: (str) year of the research collaboration, `organizations`: (list of str) list of organizations involved in the research collaboration."
            )
            technology_licensing: List[Dict[str, str]] = Field(
                description="Planned act in which one organization grants permission to another organization to use its intellectual property, such as patents, trademarks, or proprietary technology, in exchange for a fee or royalty. Return `name`: (str) name of the technology licensing (organization), `description`: (str) description of the technology licensing, `year`: (str) year of the technology licensing, `organizations`: (list of str) list of organizations involved in the technology licensing."
            )
            distribution_agreements: List[Dict[str, str]] = Field(
                description="Planned act in which one organization agrees to distribute the products or services of another organization, typically in a specific geographic region or market segment. Return `name`: (str) name of the distribution agreement (organization), `description`: (str) description of the distribution agreement, `year`: (str) year of the distribution agreement, `organizations`: (list of str) list of organizations involved in the distribution agreement."
            )

        return self.extract_data_from_perplexity(
            organization_name=parameters.organization_name,
            metadata=parameters.metadata,
            use_cache=parameters.use_cache,
            answer_format=AnswerFormat,
            topic_name="strategic_alliances",
            model="sonar-pro",
            temperature=0,
            add_source=True,
        )

    def get_organization_profit_and_loss(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            revenue: List[Dict[str, str]] = Field(
                description="Revenue: Annual revenue/turnover of the organization per year by currency. Return `currency` (str), `year` (int), `value` (int), `label` (str) value of the revenue in human readable format, `source` (str) name of the source where you found this information, `source_url` (str) url of the source where you found this information."
            )
            expenses: List[Dict[str, str]] = Field(
                description="Expenses: Annual expenses of the organization per year by currency. Return `currency` (str), `year` (int), `value` (int), `label` (str) value of the expenses in human readable format, `source` (str) name of the source where you found this information, `source_url` (str) url of the source where you found this information."
            )
            profit: List[Dict[str, str]] = Field(
                description="Profit: Annual profit/loss of the organization per year by currency. Return `currency` (str), `year` (int), `value` (int), `label` (str) value of the profit in human readable format, `source` (str) name of the source where you found this information, `source_url` (str) url of the source where you found this information."
            )
            ebitda: List[Dict[str, str]] = Field(
                description="EBITDA: Annual EBITDA of the organization per year by currency. Return `currency` (str), `year` (int), `value` (int), `label` (str) value of the EBITDA in human readable format, `source` (str) name of the source where you found this information, `source_url` (str) url of the source where you found this information."
            )

        return self.extract_data_from_perplexity(
            organization_name=parameters.organization_name,
            metadata=parameters.metadata,
            use_cache=parameters.use_cache,
            answer_format=AnswerFormat,
            topic_name="profit_and_loss",
            model="sonar-pro",
            temperature=0,
            add_source=False,
        )

    def get_organization_key_indicators(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            key_indicators: List[Dict[str, str]] = Field(
                description="Measurable values that demonstrates how effectively an organization is achieving key business objectives. Return `name`: (str) name of the indicator, `value`: (int) value of the indicator, `unit`: (str) unit of the indicator, `label`: (str) value in human readable format, `description` (str) description of the indicator"
            )

        return self.extract_data_from_perplexity(
            organization_name=parameters.organization_name,
            metadata=parameters.metadata,
            use_cache=parameters.use_cache,
            answer_format=AnswerFormat,
            topic_name="key_indicators",
            model="sonar-pro",
            temperature=0,
            add_source=True,
        )

    def get_organization_analysis(
        self, parameters: PerplexityOrganizationParameters
    ) -> Dict:
        # Initialize storage
        output_dir, organization_id = self.init_storage(parameters.organization_name)

        # Get organization general information
        organization_general_information = self.get_organization_general_information(
            parameters
        )

        # Get organization members
        organization_members = self.get_organization_members(parameters)

        # Get organization offerings
        organization_offerings = self.get_organization_offerings(parameters)

        # Get organization capabilities
        organization_capabilities = self.get_organization_capabilities(parameters)

        # Get organization corporate structure
        organization_corporate_structure = self.get_organization_corporate_structure(
            parameters
        )

        # Get organization strategic alliances
        organization_strategic_alliances = self.get_organization_strategic_alliances(
            parameters
        )

        # Get organization profit and loss
        organization_profit_and_loss = self.get_organization_profit_and_loss(parameters)

        # Get key indicators
        organization_key_indicators = self.get_organization_key_indicators(parameters)

        # Concatenate all data
        data = {
            "organization_name": parameters.organization_name,
            "organization_metadata": parameters.metadata,
            "organization_id": organization_id,
            "organization_storage_path": str(output_dir),
            "organization_general_information": organization_general_information.get(
                "response_json", {}
            ),
            "organization_members": organization_members.get("response_json", {}),
            "organization_offerings": organization_offerings.get("response_json", {}),
            "organization_capabilities": organization_capabilities.get(
                "response_json", {}
            ),
            "organization_corporate_structure": organization_corporate_structure.get(
                "response_json", {}
            ),
            "organization_strategic_alliances": organization_strategic_alliances.get(
                "response_json", {}
            ),
            "organization_profit_and_loss": organization_profit_and_loss.get(
                "response_json", {}
            ),
            "organization_key_indicators": organization_key_indicators.get(
                "response_json", {}
            ),
            "date_extracted": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Save data to storage
        services.storage_service.put_object(
            prefix=output_dir,
            key=f"{organization_id}_organization_analysis.json",
            content=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"),
        )
        return data

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline."""
        return [
            StructuredTool(
                name="perplexity_get_organization_details",
                description="Get basic details of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_details(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
            StructuredTool(
                name="perplexity_get_organization_members",
                description="Get members of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_members(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
            StructuredTool(
                name="perplexity_get_organization_offerings",
                description="Get offerings of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_offerings(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
            StructuredTool(
                name="perplexity_get_organization_capabilities",
                description="Get capabilities of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_capabilities(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
            StructuredTool(
                name="perplexity_get_organization_corporate_structure",
                description="Get corporate structure of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_corporate_structure(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
            StructuredTool(
                name="perplexity_get_organization_strategic_alliances",
                description="Get strategic alliances of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_strategic_alliances(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
            StructuredTool(
                name="perplexity_get_organization_profit_and_loss",
                description="Get profit and loss of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_profit_and_loss(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
            StructuredTool(
                name="perplexity_get_organization_key_indicators",
                description="Get key indicators of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_key_indicators(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
            StructuredTool(
                name="perplexity_get_organization_analysis",
                description="Get analysis of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_analysis(
                    PerplexityOrganizationParameters(**kwargs)
                ),
                args_schema=PerplexityOrganizationParameters,
            ),
        ]

    def as_api(self, router: APIRouter) -> None:
        pass


if __name__ == "__main__":
    from src import secret

    # Initialize perplexity integration
    perplexity_integration_config = PerplexityIntegrationConfiguration(
        api_key=secret.get("PERPLEXITY_API_KEY"),
    )

    # Init workflow
    workflow = PerplexityOrganizationWorkflows(
        PerplexityOrganizationWorkflowsConfiguration(
            perplexity_integration_config=perplexity_integration_config,
        )
    )

    # Run organization analysis
    organization_name = "Palantir Technologies"
    organization_metadata = {"website": "https://www.palantir.com/"}
    data = workflow.get_organization_analysis(
        PerplexityOrganizationParameters(
            organization_name=organization_name,
            metadata=organization_metadata,
            use_cache=True,
        )
    )
