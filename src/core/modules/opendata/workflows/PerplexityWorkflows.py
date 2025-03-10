from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from src.core.integrations.PerplexityIntegration import PerplexityIntegration, PerplexityIntegrationConfiguration
from abi import logger
from pydantic import Field, BaseModel
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
import json
import shutil
import os
import time

@dataclass
class PerplexityWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for OrganizationAnalysis workflow.
    
    Attributes:
        perplexity_integration_config (PerplexityIntegrationConfiguration): Configuration for Perplexity integration
        force_update (bool): Force update the data
    """
    perplexity_integration_config: PerplexityIntegrationConfiguration
    force_update: bool = Field(False, description="Force update the data")


class PerplexityOrganizationParameters(WorkflowParameters):
    """Parameters for OrganizationAnalysis workflow execution.
    
    Attributes:
        organization_name (str): Name of the organization to analyze
        website (str): Website URL of the organization
        data_store_name (str): Data store name to store the data
    """
    organization_name: str = Field(description="Name of the organization to analyze")
    website: str = Field(description="Website URL of the organization")
    data_store_name: Optional[str] = Field("storage/datalake/opendata/organizations", description="Data store name to store the data")
    details: bool = Field(False, description="Whether to include details in the response")

class PerplexityMarketDetailsParameters(WorkflowParameters):
    """Parameters for MarketDetails workflow execution.
    
    Attributes:
        market_name (str): Name of the market to analyze
        description (str): Description of the market
        data_store_name (str): Data store name to store the data
    """
    market_name: str = Field(description="Name of the market to analyze")
    description: str = Field(description="Description of the market")
    data_store_name: Optional[str] = Field("storage/datalake/opendata/markets", description="Data store name to store the data")
    details: bool = Field(False, description="Whether to include details in the response")

class PerplexityIndustryDetailsParameters(WorkflowParameters):
    """Parameters for IndustryDetails workflow execution.
    
    Attributes:
        industry_name (str): Name of the industry to analyze
        data_store_name (str): Data store name to store the data
    """
    industry_name: str = Field(description="Name of the industry to analyze")
    data_store_name: Optional[str] = Field("storage/datalake/opendata/industries", description="Data store name to store the data")
    details: bool = Field(True, description="Whether to include details in the response")

class PerplexityWorkflows(Workflow):
    """Workflow for analyzing organizations and mapping them to an ontology using Perplexity."""
    
    __configuration: PerplexityWorkflowsConfiguration
        
    def __init__(self, configuration: PerplexityWorkflowsConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__perplexity = PerplexityIntegration(self.__configuration.perplexity_integration_config)

    def __create_id_from_name(self, name: str) -> str:
        """Create an id from a name."""
        return name.lower().replace(" ", "_").replace(".", "")

    def _init_storage(self, name: str, data_store_name: str):
        """Initialize the storage for the workflow."""
        # Generate dir path
        object_id = self.__create_id_from_name(name)
        dir_path = Path(data_store_name) / object_id

        # Create directory if it doesn't exist
        os.makedirs(dir_path, exist_ok=True)

        # Return object id and dir path
        return object_id, dir_path
    
    def extract_json_from_completion(self, completion_text: str) -> dict:
        """Extract JSON object from completion text that contains markdown formatting.
        
        Args:
            completion_text (str): Raw completion text containing JSON in markdown format
            
        Returns:
            dict: Parsed JSON object
        """
        # Find JSON content between ```json and ``` markers
        json_start = completion_text.find("```json\n") + len("```json\n")
        json_end = completion_text.rfind("\n```")
        
        if json_start == -1 or json_end == -1:
            json_str = completion_text
        else:
            json_str = completion_text[json_start:json_end]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse JSON: {str(e)}.")
            return {}
    
    def extract_data_from_perplexity(
        self, 
        subject_name: str,
        subject_type: str,
        data_store_name: str, 
        answer_format: BaseModel,
        topic_name: str,
        metadata: Dict,
        model: str = "sonar",
        temperature: float = 0,
        details: bool = False,
        search_domain_filter: List[str] = ["perplexity.ai"]
    ) -> None:
        """Extract data from Perplexity."""
        # Init
        topic_id = self.__create_id_from_name(topic_name)

        # Generate dir path from subject name
        subject_id, dir_path = self._init_storage(subject_name, data_store_name)

        # Generate file path to store data
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        file_path = dir_path / f"_perplexity_{subject_id}_{topic_id}"
        file_path_history = dir_path / f"_{timestamp}_perplexity_{subject_id}_{topic_id}"
        file_response_path = dir_path / f"_perplexity_response_{subject_id}_{topic_id}"

        # Check if data already exists
        if os.path.exists(file_path.with_suffix('.json')) and not self.__configuration.force_update:
            logger.info(f"Using existing Perplexity response for {subject_name} - {topic_name}")
            try:
                with open(file_response_path.with_suffix('.json'), "r") as f:
                    response_json = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load existing Perplexity response for {subject_name} - {topic_name}: {str(e)}")
                response_json = {}
        else:
            details_str = "`explanation`: A detailed explanation of the analysis, `source`: The name of the source used for this information, `source_url`: The URL of the source used for this information, `source_date`: The date of the source used for this information."
            if details:
                prompt = f"""Analyze the {subject_type}: '{subject_name}' ({', '.join([f'{k}: {v}' for k,v in metadata.items()])}).
Please output a JSON object containing the following fields:
{', '.join([f'"{field}": {answer_format.model_fields[field].description}, {details_str}' for field in answer_format.model_fields.keys()])}"""
            else:
                prompt = f"""Analyze the {subject_type}: '{subject_name}' ({', '.join([f'{k}: {v}' for k,v in metadata.items()])}).
Please output a JSON object containing the following fields:
{', '.join([f'"{field}": {answer_format.model_fields[field].description}' for field in answer_format.model_fields.keys()])}"""
            system_prompt = """You are a helpful AI assistant. 
            
            Rules: 
            1. Provide only the final answer. It is important that you do not include any explanation on the steps below. 
            2. Do not show the intermediate steps information.
            3. Be precise and exhaustive.
            4. Do not include any information that is not related to the question.
            5. Verify the information you provide is correct and accurate.
            """
            response_format = {
                "type": "json_schema",
                "json_schema": {"schema": answer_format.model_json_schema()}
            }
            if metadata.get("website"):
                search_domain_filter.append(metadata["website"].split("www.")[1].split("/")[0])
            logger.info(f"Extracting data from Perplexity for {subject_name} - {topic_name}")
            try:
                response = self.__perplexity.ask_question(prompt, system_prompt=system_prompt, temperature=temperature, response_format=response_format, model=model, search_domain_filter=search_domain_filter)
                time.sleep(5)
            except Exception as e:
                logger.error(f"Failed to extract data from Perplexity for {subject_name} - {topic_name}: {str(e)}")
                return {}
            
            # Save response to file with timestamp - using with_suffix() for file extensions
            with open(file_path.with_suffix('.txt'), "w") as f:
                f.write(response)
            shutil.copy(file_path.with_suffix('.txt'), file_path_history.with_suffix('.txt'))

            # Save data to JSON file - using with_suffix() for file extensions
            data = {
                "subject_id": subject_id,
                "subject_name": subject_name,
                "subject_type": subject_type,
                "metadata": metadata,
                "topic_id": topic_id,
                "topic_name": topic_name,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "model": model,
                "temperature": temperature,
                "response_format": response_format,
                "response": response,
            }
            with open(file_path.with_suffix('.json'), "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            shutil.copy(file_path.with_suffix('.json'), file_path_history.with_suffix('.json'))

            # Extract response JSON
            logger.info(f"Parsing Perplexity response for {subject_name} - {topic_name}")
            response_json = self.extract_json_from_completion(response)

            # Save response to file
            logger.info(f"Saving Perplexity response for {subject_name} - {topic_name}")
            with open(file_response_path.with_suffix('.json'), "w") as f:
                json.dump(response_json, f, indent=4, ensure_ascii=False)
        return response_json
    
    def get_organization_details(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            name: str = Field(description="A Designative Name that is an official name for a particular entity. Return `name`: (str) name of the organization.") # Proper Name (ont00001014)
            legal_name: str = Field(description="A Proper Name that is an official name for the designated entity as determined by a Government or court of law. Return `legal_name`: (str) legal name of the organization.") # Legal Name (ont00001331)
            website: str = Field(description="Website URL of the organization. Return `website`: (str) website URL of the organization.")
            mission: str = Field(description="Describes the core purpose and primary objectives of an organization, explaining what it does, whom it serves, and how it serves them. Return `mission`: (str) mission of the organization.")
            vision: str = Field(description="Outlines the long-term aspirations or desired future state of an organization. It serves as a guiding star for strategic planning and decision-making. Return `vision`: (str) vision of the organization.")
            created_date: Dict[str, str] = Field(description="Date when organization was created. Return `day`: (str) day when organization was created, `month`: (str) month when organization was created, `year`: (str) year when organization was created.")
            headquarters: List[Dict[str, str]] = Field(description="Global and regional headquarters locations. Return `name`: (str) name of the facility, `type`: (str) either 'Global Headquarters' or 'Regional Headquarters', `description`: (str) description of the facility, `country`: (str) country name, `state`: (str) state name, `city`: (str) city name, and `address`: (str) address.")
            number_of_employee: int = Field(description="Number of employees working in the organization. Return `number_of_employee`: (int) number of employees in the organization.")
            industries: List[Dict[str, str]] = Field(description="A Group of Organizations that share common characteristics, activities, or business objectives. Return `name`: (str) name of the industry, `definition`: (str) definition of the industry.")
            ticker_symbol: str = Field(description="A stock symbol (or ticker symbol) is a unique series of letters assigned to a security for trading purposes. Return `ticker_symbol`: (str) ticker symbol of the organization (e.g. AAPL, TSLA, etc).")
            stock_market: str = Field(description="Stock market where the organization's stock is traded. Return `stock_market`: (str) stock market name where the organization's stock is traded (NYSE, NASDAQ, etc).")
        
        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="details",
            metadata={"website": parameters.website},
            model="sonar-pro"
        )
    
    def get_organization_offerings(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            products: List[Dict[str, List[str]]] = Field(description="Tangible items that are created, manufactured, or sourced to satisfy a want or need by the organization. Return `name`: (str) name of the product or category of products, `description`: (str) description of the product.")
            services: List[Dict[str, List[str]]] = Field(description="Intangible activities or benefits provided by one party to another, often to solve a problem or meet a need by the organization. Return `name`: (str) name of the service, `description`: (str) description of the service.")
            markets: List[Dict[str, List[str]]] = Field(description="Represents the organization's economic space where buyers and sellers interact to exchange goods, services, or information, typically characterized by supply and demand dynamics. Return `name` (str), `definition` (str): market definition, `products`: (list of str) Organization listed products in the market, `services`: (list of str) Organization listed services in the market.")
            market_segments: List[Dict[str, List[str]]] = Field(description="Represents a subset of a market, defined by specific characteristics or criteria that distinguish it from other segments, often based on consumer needs, preferences, or demographics. Return `name` (str), `definition` (str), `market`: (str) name of the market where the segment is, `products`: (list of str) Organization listed products in the market segment, `services`: (list of str) Organization listed services in the market segment.")
            positionings: List[Dict[str, List[str]]] = Field(description="Role that represents the strategic position and differentiation strategy of the organization within its market, highlighting how the organization distinguishes itself from competitors and is perceived by its target audience. Return `name`: (str) `description`: (str), `market`: (list) name of the market where the positioning is.")

        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="offerings",
            metadata={"website": parameters.website},
            model="sonar",
            details=parameters.details
        )
    
    def get_organization_capabilities(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            technological_capabilities: List[Dict[str, str]] = Field(description="Abilities and functionalities possessed by machines, software, or systems. Return `name`: (str) name of the capability, `description`: (str) description of the capability, `explanation`: (str) explanation of the capability, `source`: (str) name of the source where you found this information, `source_url`: (str) url of the source where you found this information.")
            human_capabilities: List[Dict[str, str]] = Field(description="Skills, knowledge, and abilities possessed by human beings. Return `name`: (str) name of the capability, `description`: (str) description of the capability, `explanation`: (str) explanation of the capability, `source`: (str) name of the source where you found this information, `source_url`: (str) url of the source where you found this information.")

        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="capabilities",
            metadata={"website": parameters.website},
            model="sonar",
            details=parameters.details
        )
    
    def get_organization_members(
        self, 
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            board_of_directors: List[Dict[str, str]] = Field(description="The board of directors is a governing body elected by shareholders (in a corporation) to oversee the organization's management. It represents the interests of shareholders and ensures the company's prosperity by collectively directing its affairs. Return all board of directors members with `name`: (str) name of the member, `position`: (str) position of the member")
            executive_committee: List[Dict[str, str]] = Field(description="The executive committee are members of the board of directors or top management that are empowered to make certain decisions on behalf of the board or management team. Return all executive committee members with `name`: (str) name of the member, `position`: (str) position of the member")
            top_management: List[Dict[str, str]] = Field(description="Top management refers to the highest level of managers within an organization who are responsible for controlling and overseeing the entire organization. They make strategic decisions that affect the company's direction and success. Return all top management members with `name`: (str) name of the member, `position`: (str) position of the member")
            # ceo: Dict[str, str] = Field(description="Chief Executive Officer (CEO) is the highest-ranking executive in a company, responsible for overseeing the company's operations and making strategic decisions. Return `name`: (str) name of the CEO, `start_date`: (str) start date of the CEO")
            # president: Dict[str, str] = Field(description="President is the second-highest-ranking executive in a company, responsible for overseeing the company's operations and making strategic decisions. Return `name`: (str) name of the president, `start_date`: (str) start date of the president")
            # cfo: Dict[str, str] = Field(description="Chief Financial Officer (CFO) is the highest-ranking financial executive in a company, responsible for overseeing the company's financial operations and making strategic decisions. Return `name`: (str) name of the CFO, `start_date`: (str) start date of the CFO")
            # cto: Dict[str, str] = Field(description="Chief Technology Officer (CTO) is the highest-ranking technology executive in a company, responsible for overseeing the company's technology operations and making strategic decisions. Return `name`: (str) name of the CTO, `start_date`: (str) start date of the CTO")
            # chairman: Dict[str, str] = Field(description="Chairman is the highest-ranking executive in a company, responsible for overseeing the company's operations and making strategic decisions. Return `name`: (str) name of the chairman, `start_date`: (str) start date of the chairman")
        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="members",
            metadata={"website": parameters.website},
            model="sonar-pro",
            details=parameters.details,
            search_domain_filter=[]
        )
    
    def get_organization_profit_and_loss(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            revenue: List[Dict[str, str]] = Field(description="Revenue: Annual revenue/turnover of the organization per year by currency. Return `currency` (str), `year` (int), `value` (int), `label` (str) value of the revenue in human readable format, `source` (str) name of the source where you found this information, `source_url` (str) url of the source where you found this information.")
            expenses: List[Dict[str, str]] = Field(description="Expenses: Annual expenses of the organization per year by currency. Return `currency` (str), `year` (int), `value` (int), `label` (str) value of the expenses in human readable format, `source` (str) name of the source where you found this information, `source_url` (str) url of the source where you found this information.")
            profit: List[Dict[str, str]] = Field(description="Profit: Annual profit/loss of the organization per year by currency. Return `currency` (str), `year` (int), `value` (int), `label` (str) value of the profit in human readable format, `source` (str) name of the source where you found this information, `source_url` (str) url of the source where you found this information.")
            ebitda: List[Dict[str, str]] = Field(description="EBITDA: Annual EBITDA of the organization per year by currency. Return `currency` (str), `year` (int), `value` (int), `label` (str) value of the EBITDA in human readable format, `source` (str) name of the source where you found this information, `source_url` (str) url of the source where you found this information.")
        
        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="profit_and_loss",
            metadata={"website": parameters.website},
            model="sonar-pro",
            details=parameters.details
        )
    
    def get_organization_key_indicators(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            key_indicators: List[Dict[str, str]] = Field(description="Measurable values that demonstrates how effectively an organization is achieving key business objectives. Return `name`: (str) name of the indicator, `value`: (int) value of the indicator, `unit`: (str) unit of the indicator, `label`: (str) value in human readable format, `description`: (str) description of the indicator, `source`: (str) name of the source where you found this information, `source_url`: (str) url of the source where you found this information.")
        
        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="key_indicators",
            metadata={"website": parameters.website},
            model="sonar-pro",
            details=parameters.details
        )
    
    def get_organization_corporate_structure(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):       
            mergers: List[Dict[str, str]] = Field(description="A Social Act involving the consolidation of two or more organizations into a single entity. Return `name`: (str) name of the organization's merger, `description`: (str) description of the merger terms, `year`: (int) year of the merger, `organizations`: (list of str) list of organizations involved in the merger.")
            acquisitions: List[Dict[str, str]] = Field(description="A Social Act involving one organization purchasing another organization or its assets. Return `name`: (str) name of the organization's acquisition, `description`: (str) description of the acquisition terms, `year`: (int) year of the acquisition, `organizations`: (list of str) list of organizations involved in the acquisition.")
            subsidiaries: List[Dict[str, str]] = Field(description="A Social Act in which an organization establishes a new subsidiary entity, typically to expand its operations, enter new markets, or achieve strategic objectives. Return `name`: (str) name of the subsidiary (organization), `mission`: (str) mission of the subsidiary, `year`: (int) year of the establishment of the subsidiary.")
        
        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="corporate_structure",
            metadata={"website": parameters.website},
            model="sonar-pro",
            details=parameters.details
        )
    
    def get_organization_facilities(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            headquarters: List[Dict[str, str]] = Field(description="Global and regional headquarters locations. Return `name`: (str) name of the facility, `type`: (str) either 'Global Headquarters' or 'Regional Headquarters', `description`: (str) description of the facility, `country`: (str) country name, `state`: (str) state name, `city`: (str) city name, and `address`: (str) address.")
            offices: List[Dict[str, str]] = Field(description="Office buildings used for commercial or administrative work. Return 3 main offices with `name`: name of the office, `size`: (str) number of workers, `country`: (str) country name, `state`: (str) state name, `city`: (str) city name, and `address`: (str) address.")
            factories: List[Dict[str, str]] = Field(description="Manufacturing or production facilities. Return 3 main factories with `name`: name of the factory, `size`: (str) number of employees, `country`: (str) country name, `state`: (str) state name, `city`: (str) city name, and `address`: (str) address.")
        
        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization", 
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="facilities",
            metadata={"website": parameters.website},
            model="sonar",
            details=parameters.details
        )

    def get_organization_strategic_alliances(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            partnerships: List[Dict[str, str]] = Field(description="An Act of Association in which two or more organizations or individuals enter into an agreement to cooperate for mutual benefit, typically to achieve shared objectives. Return `name`: (str) name of the partnership (organization), `description`: (str) description of the partnership, `organizations`: (list of str) list of organizations involved in the partnership")
            joint_ventures: List[Dict[str, str]] = Field(description="An Act of Association wherein two or more organizations come together to undertake a specific project or business activity, sharing resources, risks, and rewards, while maintaining their distinct legal identities. Return `name`: (str) name of the organization, `description`: (str) description of the joint venture terms, `year`: (int) year of the joint venture, `organizations`: (list of str) list of organizations involved in the joint venture.")
            marketing_alliances: List[Dict[str, str]] = Field(description="An Act of Association in which two or more organizations enter into a cooperative relationship to promote and distribute products or services to a common audience. Return `name`: (str) name of the marketing alliance (organization), `description`: (str) description of the marketing alliance, `organizations`: (list of str) list of organizations involved in the marketing alliance.")
            research_collaborations: List[Dict[str, str]] = Field(description="An Act of Association in which two or more organizations enter into a cooperative relationship to conduct research or development projects, sharing resources, expertise, and results. Return `name`: (str) name of the research collaboration (organization), `description`: (str) description of the research collaboration, `organizations`: (list of str) list of organizations involved in the research collaboration.")
            technology_licensing: List[Dict[str, str]] = Field(description="An Act of Association in which one organization grants permission to another organization to use its intellectual property, such as patents, trademarks, or proprietary technology, in exchange for a fee or royalty. Return `name`: (str) name of the technology licensing (organization), `description`: (str) description of the technology licensing, `organizations`: (list of str) list of organizations involved in the technology licensing.")
            distribution_agreements: List[Dict[str, str]] = Field(description="An Act of Association in which one organization agrees to distribute the products or services of another organization, typically in a specific geographic region or market segment. Return `name`: (str) name of the distribution agreement (organization), `description`: (str) description of the distribution agreement, `organizations`: (list of str) list of organizations involved in the distribution agreement.")
        
        return self.extract_data_from_perplexity(
            subject_name=parameters.organization_name,
            subject_type="organization",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="strategic_alliances",
            metadata={"website": parameters.website},
            model="sonar-pro",
            details=parameters.details
        )
    
    def get_organization_analysis(
        self,
        parameters: PerplexityOrganizationParameters
    ) -> Dict:
        # Initialize storage
        organization_id, dir_path = self._init_storage(parameters.organization_name, parameters.data_store_name)
        file_path = dir_path / f"{organization_id}_organization_analysis"

        logger.info(f"-----> Initializing storage for {parameters.organization_name}")
    
        # Get organization details
        logger.info(f"-----> Getting organization details")
        organization_details = self.get_organization_details(parameters)
        industries = organization_details.get("industries")
        organization_industries_analysis = []
        for industry in industries:
            # Get industries analysis
            logger.info(f"-----> Getting organization industry analysis: {industry}")
            organization_industries_analysis.append(self.get_industry_analysis(PerplexityIndustryDetailsParameters(
                industry_name=industry,
                details=parameters.details
            )))

        # Get offerings
        logger.info(f"-----> Getting organization offerings")
        organization_offerings = self.get_organization_offerings(parameters)

        # Get markets analysis
        organization_markets_analysis = []
        for market in organization_offerings.get("markets", []):
            market_name = market.get("name", "")
            market_description = market.get("definition", "")
            market_analysis = self.get_market_analysis(PerplexityMarketDetailsParameters(
                market_name=market_name,
                description=market_description,
                details=parameters.details
            ))
            organization_markets_analysis.append(market_analysis)

        # Get capabilities
        logger.info(f"-----> Getting organization capabilities")
        organization_capabilities = self.get_organization_capabilities(parameters)

        # Get members
        logger.info(f"-----> Getting organization members")
        organization_members = self.get_organization_members(parameters)

        # Get financials
        logger.info(f"-----> Getting organization profit and loss")
        organization_profit_and_loss = self.get_organization_profit_and_loss(parameters)

        # Get key indicators
        logger.info(f"-----> Getting organization key indicators")
        organization_key_indicators = self.get_organization_key_indicators(parameters)

        # Get corporate structure
        logger.info(f"-----> Getting organization corporate structure")
        organization_corporate_structure = self.get_organization_corporate_structure(parameters)
        
        # Get facilities
        logger.info(f"-----> Getting organization facilities")
        organization_facilities = self.get_organization_facilities(parameters)

        # Get strategic alliances
        logger.info(f"-----> Getting organization strategic alliances")
        organization_strategic_alliances = self.get_organization_strategic_alliances(parameters)

        # Concatenate all data
        data = {
            "organization_id": organization_id,
            "organization_name": parameters.organization_name,
            "organization_website": parameters.website,
            "organization_details": organization_details,
            "organization_offerings": organization_offerings,
            "organization_capabilities": organization_capabilities,
            "organization_members": organization_members,
            "organization_profit_and_loss": organization_profit_and_loss,
            "organization_key_indicators": organization_key_indicators,
            "organization_corporate_structure": organization_corporate_structure,
            "organization_facilities": organization_facilities,
            "organization_strategic_alliances": organization_strategic_alliances,
            "organization_industries_analysis": organization_industries_analysis,
            "organization_markets_analysis": organization_markets_analysis,
        }

        # Save data to JSON file
        logger.info(f"-----> Saving organization analysis to {file_path.with_suffix('.json')}")
        with open(file_path.with_suffix('.json'), "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return data
    
    def get_market_details(
        self,
        parameters: PerplexityMarketDetailsParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            market_size: List[Dict[str, str]] = Field(description="Market size: Volume of sales, revenue, or other relevant metrics. Return `metric`: (str) metric used to measure the market size, `value`: (int) value of the metric, `unit`: (str) unit of the metric, `currency`: (str) currency of the metric, `year`: (int) year, ")
            market_segments: List[Dict[str, str]] = Field(description="Represents a subset of a market, defined by specific characteristics or criteria that distinguish it from other segments, often based on consumer needs, preferences, or demographics. Return `name`: (str) name of the segment, `description`: (str) description of the segment, `market_size`: (str) market size of the segment.")
            cagr: List[Dict[str, str]] = Field(description="Compound annual growth rate (CAGR) of the market. Return `value`: (float) CAGR, `unit`: (str) unit of the CAGR, `year`: (int) year.")
            key_drivers: List[Dict[str, str]] = Field(description="A factor or influence that has a significant impact on the performance or direction of a market, industry, or organization. Return `name`: (str) name of the driver, `description`: (str) description of the driver.")
            key_trends: List[Dict[str, str]] = Field(description="A general direction or pattern of change observed in a market, industry, or organization over time. Return `name`: (str) name of the trend, `description`: (str) description of the trend.")
            key_challenges: List[Dict[str, str]] = Field(description="An obstacle or difficulty that must be overcome by an organization, market, or industry to achieve its objectives. Return `name`: (str) name of the challenge, `description`: (str) description of the challenge.")

        return self.extract_data_from_perplexity(
            subject_name=parameters.market_name,
            subject_type="market",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="details",
            metadata={"description": parameters.description},
            model="sonar-pro",
            details=parameters.details
        )
    
    def get_market_players(
        self,
        parameters: PerplexityMarketDetailsParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            competitors: List[Dict[str, str]] = Field(description="A group of organizations that create products or services that compete against each other within the same market. Return 5 main competitors `name`: (str) name of the competitor (organization), `market_segments`: (list of str) list of market segments where the competitor operates")
            consumers: List[Dict[str, str]] = Field(description="A group of agents (people or organizations) that purchase goods or services from other businesses in the market. Return 5 main consumers or group of consumers `name`: (str) name of the consumer (organization), `market_segments`: (list of str) list of market segments where the consumer operates")
            distributors: List[Dict[str, str]] = Field(description="A group of organizations that distribute products from manufacturers to retailers or directly to consumers. Return 5 main distributors `name`: (str) name of the distributor (organization), `market_segments`: (list of str) list of market segments where the distributor operates")
            suppliers: List[Dict[str, str]] = Field(description="A group of organizations that provide raw materials, components, or services to other businesses. Return 5 main suppliers `name`: (str) name of the supplier (organization), `market_segments`: (list of str) list of market segments where the supplier operates")
            regulators: List[Dict[str, str]] = Field(description="A group of government agencies that set rules and regulations for businesses in the market. Return main regulators `name`: (str) name of the regulator (organization), `market_segments`: (list of str) list of market segments where the regulator operates")
            investors: List[Dict[str, str]] = Field(description="A group of organizations that provide capital to businesses in exchange for equity or expected financial returns. Return main investors `name`: (str) name of the investor (organization), `market_segments`: (list of str) list of market segments where the investor operates")
            
        return self.extract_data_from_perplexity(
            subject_name=parameters.market_name,
            subject_type="market",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="players",
            metadata={"description": parameters.description},
            model="sonar",
            details=parameters.details
        )
    
    def get_market_risks_and_opportunities(
        self,
        parameters: PerplexityMarketDetailsParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            key_opportunities: List[Dict[str, str]] = Field(description="A favorable set of circumstances or a possibility that, if leveraged, could lead to a positive outcome or advantage for an organization. Return `name`: (str) name of the opportunity, `description` (str).")
            key_risks: List[Dict[str, str]] = Field(description="A potential event or condition that, if it occurs, could have a negative impact on an organization's ability to achieve its objectives. Return `name`: (str) name of the risk, `description` (str).")

        return self.extract_data_from_perplexity(
            subject_name=parameters.market_name,
            subject_type="market",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="risks_and_opportunities",
            metadata={"description": parameters.description},
            model="sonar",
            details=parameters.details
        )
    
    def get_market_analysis(
        self,
        parameters: PerplexityMarketDetailsParameters
    ) -> Dict:
        # Initialize storage
        market_id, dir_path = self._init_storage(parameters.market_name, parameters.data_store_name)
        file_path = dir_path / f"{market_id}_market_analysis"
        logger.info(f"-----> Initializing storage for {parameters.market_name}")
        
        # Get market data
        logger.info(f"-----> Getting market details")
        market_details = self.get_market_details(parameters)

        # Get market players
        logger.info(f"-----> Getting market players")
        market_players = self.get_market_players(parameters)

        # Get market risks and opportunities
        logger.info(f"-----> Getting market risks and opportunities")
        market_risks_and_opportunities = self.get_market_risks_and_opportunities(parameters)

        # Concatenate all data
        data = {
            "market_id": market_id,
            "market_name": parameters.market_name,
            "market_description": parameters.description,
            "market_details": market_details,
            "market_players": market_players,
            "market_risks_and_opportunities": market_risks_and_opportunities,
        }

        # Save data to JSON file
        logger.info(f"-----> Saving market analysis to {file_path.with_suffix('.json')}")
        with open(file_path.with_suffix('.json'), "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return data
    
    def get_industry_structure(
        self,
        parameters: PerplexityIndustryDetailsParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            industry_definition: str = Field(description="Definition of the industry. Return `definition`: (str) definition of the industry.")
            industry_concentration: str = Field(description="Type of market structure (e.g. oligopoly, monopolistic competition, perfect competition). Return `structure`: (str) market structure type, `description`: (str) explanation of the structure.")
            major_organizations: List[Dict[str, str]] = Field(description="Large organizations with substantial market share and industry leadership. Return the 5 main organizations in the industry. `name`: (str) name of the organization, `description`: (str) description of organization's role and position, `market_share`: (str) approximate market share if available in percentage, `key_strengths`: (list of str) areas where they lead like revenue, innovation, brand recognition")
            small_medium_enterprises: List[Dict[str, str]] = Field(description="Smaller organizations specializing in niche markets or services. Return the 5 main organizations in the industry. `name`: (str) name of the organization, `description`: (str) description of specialization and role, `niche_market`: (str) specialized market segment they serve, `innovations`: (list of str) notable innovations or contributions to industry")
            entry_barriers: List[Dict[str, str]] = Field(description="Barriers preventing new entrants. Return `barrier`: (str) barrier name, `description`: (str) barrier description, `impact`: (str) impact on competition.")

        return self.extract_data_from_perplexity(
            subject_name=parameters.industry_name,
            subject_type="industry",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="structure",
            metadata={},
            model="sonar",
            details=parameters.details
        )

    def get_industry_demand_and_growth(
        self,
        parameters: PerplexityIndustryDetailsParameters  
    ) -> Dict:
        class AnswerFormat(BaseModel):
            market_size: Dict[str, str] = Field(description="Industry market size and growth. Return `current_size`: (str) current market value, `growth_rate`: (str) annual growth rate, `forecast`: (str) future projections.")
            customer_segments: List[Dict[str, str]] = Field(description="Major customer segments. Return `segment`: (str) segment name, `needs`: (list[str]) key needs/requirements, `size`: (str) segment size.")
            demand_factors: List[Dict[str, str]] = Field(description="Factors affecting demand. Return `factor`: (str) factor name, `impact`: (str) impact description, `trend`: (str) current trend.")

        return self.extract_data_from_perplexity(
            subject_name=parameters.industry_name,
            subject_type="industry", 
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="demand_and_growth",
            metadata={},
            model="sonar-pro",
            details=parameters.details
        )

    def get_industry_technology(
        self,
        parameters: PerplexityIndustryDetailsParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            tech_advancement: Dict[str, str] = Field(description="Technology state in industry. Return `level`: (str) advancement level, `description`: (str) technology landscape, `trends`: (list[str]) key technological trends.")
            innovation_metrics: Dict[str, str] = Field(description="Innovation indicators. Return `r_d_investment`: (str) R&D investment level, `innovation_rate`: (str) innovation frequency, `key_areas`: (list[str]) main innovation areas.")
            tech_impact: List[Dict[str, str]] = Field(description="Technology's industry impact. Return `area`: (str) affected area, `impact`: (str) impact description, `future_implications`: (str) future outlook.")

        return self.extract_data_from_perplexity(
            subject_name=parameters.industry_name,
            subject_type="industry",
            data_store_name=parameters.data_store_name, 
            answer_format=AnswerFormat,
            topic_name="technology",
            metadata={},
            model="sonar",
            details=parameters.details
        )

    def get_industry_regulations(
        self,
        parameters: PerplexityIndustryDetailsParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            key_regulations: List[Dict[str, str]] = Field(description="Major regulations. Return `regulation`: (str) regulation name, `description`: (str) requirements, `impact`: (str) business impact.")
            compliance_requirements: List[Dict[str, str]] = Field(description="Compliance needs. Return `requirement`: (str) requirement name, `description`: (str) details, `cost_impact`: (str) implementation cost impact.")
            regulatory_changes: List[Dict[str, str]] = Field(description="Potential regulation changes. Return `change`: (str) proposed change, `likelihood`: (str) probability, `impact`: (str) potential impact.")

        return self.extract_data_from_perplexity(
            subject_name=parameters.industry_name,
            subject_type="industry",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="regulations",
            metadata={},
            model="sonar",
            details=parameters.details
        )

    def get_industry_economics(
        self,
        parameters: PerplexityIndustryDetailsParameters
    ) -> Dict:
        class AnswerFormat(BaseModel):
            profitability: Dict[str, str] = Field(description="Industry profitability metrics. Return `average_margin`: (str) typical profit margin, `trend`: (str) margin trend, `factors`: (list[str]) key factors affecting profitability.")
            cost_structure: Dict[str, str] = Field(description="Main cost components. Return `fixed_costs`: (list[str]) major fixed costs, `variable_costs`: (list[str]) major variable costs, `cost_drivers`: (list[str]) key cost drivers.")
            economic_sensitivity: Dict[str, str] = Field(description="Economic cycle impact. Return `sensitivity`: (str) sensitivity level, `cycle_impact`: (str) business cycle impact, `risk_factors`: (list[str]) key economic risks.")

        return self.extract_data_from_perplexity(
            subject_name=parameters.industry_name,
            subject_type="industry",
            data_store_name=parameters.data_store_name,
            answer_format=AnswerFormat,
            topic_name="economics",
            metadata={},
            model="sonar",
            details=parameters.details
        )
        
    def get_industry_analysis(
        self,
        parameters: PerplexityIndustryDetailsParameters
    ) -> Dict:
        # Initialize storage
        industry_id, dir_path = self._init_storage(parameters.industry_name, parameters.data_store_name)
        file_path = dir_path / f"{industry_id}_industry_analysis"
        logger.info(f"-----> Initializing storage for {parameters.industry_name}")
        
        # Get industry data
        logger.info(f"-----> Getting industry structure")
        industry_structure = self.get_industry_structure(parameters)

        # Get industry demand and growth
        logger.info(f"-----> Getting industry demand and growth")
        industry_demand_and_growth = self.get_industry_demand_and_growth(parameters)

        # Get industry technology
        logger.info(f"-----> Getting industry technology")
        industry_technology = self.get_industry_technology(parameters)

        # Get industry regulations
        logger.info(f"-----> Getting industry regulations")
        industry_regulations = self.get_industry_regulations(parameters)

        # Get industry economics
        logger.info(f"-----> Getting industry economics")
        industry_economics = self.get_industry_economics(parameters)

        # Concatenate all data
        data = {
            "industry_id": industry_id,
            "industry_name": parameters.industry_name,
            "industry_structure": industry_structure,
            "industry_demand_and_growth": industry_demand_and_growth,
            "industry_technology": industry_technology,
            "industry_regulations": industry_regulations,
            "industry_economics": industry_economics,
        }

        # Save data to JSON file
        logger.info(f"-----> Saving industry analysis to {file_path.with_suffix('.json')}")
        with open(file_path.with_suffix('.json'), "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return data
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline."""
        return [
            StructuredTool(
                name="perplexity_get_organization_details",
                description="Get basic details of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_details(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_headquarters",
                description="Get headquarters information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_headquarters(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_productions_facilities",
                description="Get production facilities information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_productions_facilities(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_retail_locations",
                description="Get retail locations of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_retail_locations(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_profit_and_loss",
                description="Get profit and loss information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_profit_and_loss(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_key_indicators",
                description="Get key indicators of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_key_indicators(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_suppliers_and_customers",
                description="Get suppliers and customers information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_suppliers_and_customers(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_competitors",
                description="Get competitors information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_competitors(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_partnerships",
                description="Get partnerships information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_partnerships(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_corporate_structure",
                description="Get corporate structure information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_corporate_structure(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_offerings",
                description="Get offerings information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_offerings(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_capabilities",
                description="Get capabilities information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_capabilities(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_markets",
                description="Get markets information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_markets(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_members",
                description="Get members information of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_members(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_organization_analysis",
                description="Get complete analysis of an organization using Perplexity.",
                func=lambda **kwargs: self.get_organization_analysis(PerplexityOrganizationParameters(**kwargs)),
                args_schema=PerplexityOrganizationParameters
            ),
            StructuredTool(
                name="perplexity_get_market_details",
                description="Get detailed information about a market using Perplexity.",
                func=lambda **kwargs: self.get_market_details(PerplexityMarketDetailsParameters(**kwargs)),
                args_schema=PerplexityMarketDetailsParameters
            ),
            StructuredTool(
                name="perplexity_get_market_analysis",
                description="Get complete analysis of a market using Perplexity.",
                func=lambda **kwargs: self.get_market_analysis(PerplexityMarketDetailsParameters(**kwargs)),
                args_schema=PerplexityMarketDetailsParameters
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
    force_update = True
    workflow = PerplexityWorkflows(PerplexityWorkflowsConfiguration(
        perplexity_integration_config=perplexity_integration_config,
        force_update=force_update
    ))

    # Run organization analysis
    organization_name = "Broadcom"
    organization_website = "https://www.broadcom.com/"
    workflow.get_organization_analysis(PerplexityOrganizationParameters(
        organization_name=organization_name,
        website=organization_website,
        details=True,
    ))

    # # Run market analysis
    # market_name = "Global Sailboat Market"
    # market_description = "The market for sailboats worldwide, including monohull and multihull vessels."

    # market_name = "European Leisure Boating Market"
    # market_description = "The market for leisure boating in Europe, including river cruises and sailing holidays."
    # workflow.get_market_analysis(PerplexityMarketDetailsParameters(
    #     market_name=market_name,
    #     description=market_description,
    #     details=True,
    # ))
