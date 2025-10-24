from queue import Queue
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import Tool, BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from typing import Callable, Optional, Union, Any
from langchain_openai import ChatOpenAI  # noqa: F401
from langgraph.graph import StateGraph, START
from langgraph.graph.message import MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, BaseMessage, AIMessage
from langgraph.types import Command
from pydantic import SecretStr
from src import secret, config
from datetime import datetime
import os
from abi import logger

NAME = "PowerPoint"
DESCRIPTION = "An agent specialized in creating PowerPoint presentations."
MODEL = "gpt-4.1"
TEMPERATURE = 0
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Microsoft_Office_PowerPoint_%282019%E2%80%93present%29.svg/2203px-Microsoft_Office_PowerPoint_%282019%E2%80%93present%29.svg.png"
SYSTEM_PROMPT = """
<role>
You are PowerPoint, an agent that converts a user brief into a fully structured PowerPoint presentation using slides structure from template. 
You never invent facts; you structure, adapt, and clearly label content from the brief. 
</role>

<objective>
Create a clear, audience-aligned presentation that:
- Follows the template's structure.
- Honors the brief's objectives and constraints
</objective>

<context>
You will be provided with a template structure and user brief.
</context>

<tasks>
- Understand user's needs and create PowerPoint structure by slides using template structure.
- Generate draft slides content with sources for each slide.
- Interact with user to validate the draft, ask for missing information if needed
- Generate final presentation from slides content.
</tasks>

<operating_guidelines>
- First, carefully analyze the user brief to identify any provided information about:
1. number of slides (mandatory)
2. target audience
3. objective

- Only ask about missing information:
  - If number of slides is not specified, this must be clarified first
  - If audience or objective are partially described, acknowledge what's known and only ask about missing details
  - Never ask about information that was already clearly provided

- Generate slides structure from user brief and validate with user. 
Example:
    - Slide 0 - Title: Description
    - Slide 1 - Title: Description
    - Slide 2 - Title: Description

- Populate each slides with detailed content and template slide to use with alt text guidance if provided and return result in markdown format. 
Example:
\n**PresentationTitle: [Title]**\n
```markdown
### Slide 1: Presentation Overview
TemplateSlideUri: ppt:Slide0
\nTitle: 
\nSubtitle: 
\nDate: 
\n\n
### Slide 2: Market Dynamics
TemplateSlideUri: ppt:Slide1
\nTitle: 
\nSubtitle: 
\nQuestion: 
\nContent: 
\n\nSources:
\n\n
```
- Interact with user to validate slides content:
    - If you user wants to update slides, help him to do it and ask for validation again until he is satisfied. Then regenerate all slides content and ask for validation again.
    - Create presentation from slides content.
</operating_guidelines>

<constraints>
- You must know the number of slides to produce
- Do not talk about template structure
- Do not alter numbers; if you must round, state the rule (e.g., 1 decimal)
- Always cite data sources with source URLs
- You can only update text content of shapes, not image, video or tables.
</constraints>

--------------------------------

Slides structure from template:
[TEMPLATE_STRUCTURE]
"""

SUGGESTIONS: list[str] = []

class PowerPointState(MessagesState):
    """State class for PowerPoint presentation creation conversations.
    
    Extends MessagesState to include PowerPoint-specific information that tracks
    the presentation creation process throughout the conversation flow.
    
    Attributes:
        presentation_data (dict): Presentation data parsed from markdown
    """
    presentation_data: dict

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[Agent]:
    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get('OPENAI_API_KEY'))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    template_path = "src/marketplace/applications/powerpoint/templates/TemplateSlides.pptx"
    return PowerPointAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        memory=MemorySaver(),
        state=agent_shared_state, 
        configuration=agent_configuration,
        template_path=template_path,
    ) 

class PowerPointAgent(Agent):
    def __init__(
        self,
        name: str,
        description: str,
        chat_model: BaseChatModel,
        tools: list[Union[Tool, BaseTool, "Agent"]] = [],
        agents: list["Agent"] = [],
        memory: BaseCheckpointSaver = MemorySaver(),
        state: AgentSharedState = AgentSharedState(),
        configuration: AgentConfiguration = AgentConfiguration(),
        event_queue: Queue | None = None,
        template_path: str | None = None,
    ):
        super().__init__(
            name, 
            description, 
            chat_model, 
            tools, 
            agents, 
            memory, 
            state, 
            configuration, 
            event_queue
          )
        self.__workspace_id = config.workspace_id
        self.__storage_name = config.storage_name
        self.__template_path = template_path
        self.__template_name = os.path.basename(self.__template_path).lower().replace(".pptx", "")
        self.__datastore_path = f"datastore/powerpoint/presentations/{self.__template_name}/{datetime.now().strftime('%Y%m%d%H%M%S')}"
        

        from src.marketplace.applications.powerpoint.integrations.PowerPointIntegration import PowerPointIntegration, PowerPointIntegrationConfiguration
        self.__powerpoint_integration = PowerPointIntegration(PowerPointIntegrationConfiguration(template_path=self.__template_path))
        self.__presentation = self.__powerpoint_integration.create_presentation()

        from src.marketplace.applications.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
        self.__naas_integration = NaasIntegration(NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY")))

    def build_graph(self, patcher: Optional[Callable] = None):
        graph = StateGraph(PowerPointState)

        graph.add_node(self.current_active_agent)
        graph.add_edge(START, "current_active_agent")

        graph.add_node(self.continue_conversation)

        graph.add_node(self.inject_template_structure)

        graph.add_node(self.validate_presentation_draft)

        graph.add_node(self.call_model)

        graph.add_node(self.convert_markdown_to_shapes)

        graph.add_node(self.convert_markdown_to_json)

        graph.add_node(self.convert_json_to_ppt)

        self.graph = graph.compile(checkpointer=self._checkpointer)

    def continue_conversation(
        self, 
        state: PowerPointState
    ) -> Command:
        """
        This node continues the conversation by injecting the template structure into the system prompt.
        """
        return Command(goto="inject_template_structure")

    def inject_template_structure(
        self,
        state: PowerPointState
    ) -> Command:
        """
        This node injects the template structure into the system prompt.
        """
        if "[TEMPLATE_STRUCTURE]" in self._system_prompt:
            logger.debug("🔧 Injecting template structure")
            turtle = """
            ```turtle
            @prefix ppt: <http://ontology.naas.ai/abi/powerpoint/> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            # Presentation Overview
            ppt:Presentation a ppt:Presentation ;
                rdfs:label "Template Presentation" ;
                ppt:hasSlide ppt:Slide0, ppt:Slide1 .

            ppt:Slide0 a ppt:Slide ;
                ppt:slide_number 0 ;
                ppt:isSlideOf ppt:Presentation ;
                ppt:hasShape ppt:Shape0_6, ppt:Shape0_7, ppt:Shape0_8 .

            ppt:Shape0_6 a ppt:Shape ;
                ppt:shape_id 6 ;
                ppt:shape_type 14 ;
                ppt:shape_alt_text "Title of the presentation" ;
                ppt:shape_text "TITLE" ;
                ppt:isShapeOf ppt:Slide0 .

            ppt:Shape0_7 a ppt:Shape ;
                ppt:shape_id 7 ;
                ppt:shape_type 14 ;
                ppt:shape_alt_text "Market Intelligence and Opportunity Discovery" ;
                ppt:shape_text "Subtitle" ;
                ppt:isShapeOf ppt:Slide0 .

            ppt:Shape0_8 a ppt:Shape ;
                ppt:shape_id 8 ;
                ppt:shape_type 14 ;
                ppt:shape_alt_text "last_update_date" ;
                ppt:shape_text "YYYY-MM-DD" ;
                ppt:isShapeOf ppt:Slide0 .

            ppt:Slide1 a ppt:Slide ;
                ppt:slide_number 1 ;
                ppt:isSlideOf ppt:Presentation ;
                ppt:hasShape ppt:Shape1_2, ppt:Shape1_6, ppt:Shape1_8, ppt:Shape1_10 .

            ppt:Shape1_2 a ppt:Shape ;
                ppt:shape_id 2 ;
                ppt:shape_type 14 ;
                ppt:shape_alt_text "" ;
                ppt:shape_text "Title" ;
                ppt:isShapeOf ppt:Slide1 .

            ppt:Shape1_6 a ppt:Shape ;
                ppt:shape_id 6 ;
                ppt:shape_type 14 ;
                ppt:shape_alt_text "" ;
                ppt:shape_text "Subtitle" ;
                ppt:isShapeOf ppt:Slide1 .

            ppt:Shape1_8 a ppt:Shape ;
                ppt:shape_id 8 ;
                ppt:shape_type 14 ;
                ppt:shape_alt_text "<description>\nProduce a bullet-point list that answers the question: {{ question }}.\n</description>\n\n<constraints>\n• Output 4–6 bullet points.\n• Each bullet starts with a **short title**, followed by a colon and the explanation.\n• Separate bullets with a single `\\n` (line break).\n• Total output length must be 1 600–2 000 characters (including bullets and line breaks).\n• Example:\n-Technological transition: xxxxx\n-Balance between sustainability and performance: xxxx\n</constraints>" ;
                ppt:shape_text "Technological transition: The development and commercialization of new technologies, such as airless tires (Uptis), require substantial investments, large-scale production, and market adoption, representing a major challenge for Michelin.\nBalance between sustainability and performance: Michelin's \"All Sustainable\" approach requires finding a delicate balance between reducing carbon footprint and maintaining product performance, while remaining competitive in the market.\nDiversification of activities: Expansion into new areas, such as connected solutions and polymer composites, demands rapid adaptation and efficient integration of new skills and processes.\nSupply chain adaptation: The transition to more sustainable materials and the development of new technologies require a significant overhaul of the supply chain and production processes.\nCompetition and rapid market evolution: Faced with increased competition and rapidly evolving mobility technologies, Michelin must remain agile and innovative to maintain its leadership position.\nCost management and restructuring: The closure of factories in France, such as those in Cholet and Vannes, illustrates the challenges related to cost management and adaptation to market fluctuations, while minimizing the social impact of such decisions." ;
                ppt:isShapeOf ppt:Slide1 .

            ppt:Shape1_10 a ppt:Shape ;
                ppt:shape_id 10 ;
                ppt:shape_type 17 ;
                ppt:shape_alt_text "question" ;
                ppt:shape_text "Question" ;
                ppt:isShapeOf ppt:Slide1 .
            ```
            """
            system_prompt = self._system_prompt.replace("[TEMPLATE_STRUCTURE]", turtle)
            self.set_system_prompt(system_prompt)
        return Command(goto="validate_presentation_draft")
    
    def validate_presentation_draft(
        self,
        state: PowerPointState
    ) -> Command:
        """
        This node validates the presentation draft.
        """
        import pydash as _

        logger.debug("🔍 Validating presentation draft")

        # Get last messages
        last_human_message = self.get_last_human_message(state)
        last_ai_message : Any | None = _.find(state["messages"][::-1], lambda m: isinstance(m, AIMessage))

        if last_human_message and last_ai_message and "```markdown" in last_ai_message.content:
            # Create validation prompt
            messages: list[BaseMessage] = [SystemMessage(content=f"""
    You are a precise and logical assistant. You will be given:
    - The last user message
    - The last AI message

    Your task is to determine if the user wants to proceed with creating the presentation.
    The last user message should be an approval
    The last AI message should be a question to validate the presentation draft.

    You must answer **"true"** if the user explicitly or implicitly approves the presentation draft with content.
                                                        
    You must answer **"false"** if:
    - The user has questions or concerns about the structure
    - The user wants modifications
    - There is insufficient information to determine user's intent

    ⚠️ Very Important:
    - You must output **"true"** or **"false"** only. No explanations. No other words.
    - Your answer will be parsed by a test function and must strictly match one of those two strings.

    Now analyze the following:

    Last user message: "{last_human_message.content}"
    Last AI message: "{last_ai_message.content}"
    """)]
            
            # Get validation response
            response = self._chat_model.invoke(messages)

            if response.content == "true":
                logger.debug(f"✅ Reponse content '{response.content}'. Going to convert markdown to JSON.")
                return Command(goto="convert_markdown_to_json")
            else:
                logger.debug(f"❌ Reponse content '{response.content}'. Going back to conversation.")
        return Command(goto="call_model")
        
    def call_model(
        self, 
        state: PowerPointState
    ) -> Command:
        """
        This node handles the initial user interaction and presentation planning.
        It processes user requests and generates slide structure in markdown format.
        """
        logger.debug("🤖 Calling model")

        messages = state["messages"]
        if self._system_prompt:
            messages = [
                SystemMessage(content=self._system_prompt),
            ] + messages

        response: BaseMessage = self._chat_model_with_tools.invoke(messages)

        return Command(update={"messages": [response]})

    def convert_markdown_to_shapes(
        self,
        markdown_blocks: str,
        template_shapes: list[dict]
    ) -> dict:
        """
        This function converts markdown slide structure to shapes format.
        It parses the markdown content and extracts shapes data from template JSON.
        """
        messages: list[BaseMessage] = [SystemMessage(content=f"""
You are a precise JSON transformer. Your task is to convert markdown content into a shapes-based JSON format.

Input:
1. Markdown blocks containing slide content
2. Template JSON showing the shape structure for each slide

Instructions:
1. Understand the shapes structure from template_json.
2. Map the text in markdown content to corresponding shape by updating the "text" field of the shape. 
    If unable to find a match but you have 'text' or 'shape_alt_text' with value, try to fill it with your knowledge of the content and shape or return empty string "".
3. Maintain all other shape properties from template (shape_id, shape_type, etc.)
4. Return the extact same JSON format.

⚠️ Very Important:
- You must output the JSON format only. No explanations. No other words.
- Your answer will be parsed by a test function and must strictly match the JSON format.

Markdown content to transform:
```markdown
{markdown_blocks}
```

Template shapes to reference:
```json
{template_shapes}
```
""")]
        # Get validation response
        response = self._chat_model.invoke(messages)
        return response.content
    
    def convert_markdown_to_json(
        self, 
        state: PowerPointState
    ) -> Command:
        """
        This node converts markdown slide structure to JSON format.
        It parses the markdown content from the last message and extracts slide data.
        """
        import pydash as _
        from abi.utils.JSON import extract_json_from_completion
        from src.utils.Storage import save_text, save_json
        import json

        logger.debug("📝 Converting markdown to JSON")
        # Get last messages
        last_ai_message : Any | None = _.find(state["messages"][::-1], lambda m: isinstance(m, AIMessage))
        print("last_ai_message:", last_ai_message)
        
        # Initialize slides data list
        presentation_data: dict = {}
        slides_data: list = []
        
        if last_ai_message:
            # Extract presentation title
            content = last_ai_message.content
            if "**PresentationTitle:" in content:
                presentation_title = content.split("PresentationTitle:")[1].split("**")[0].strip()
            else:
                logger.debug("❌ No presentation title found")
                presentation_title = "Presentation"

            # Extract markdown content between ```markdown tags
            if "```markdown" not in content:
                logger.debug("❌ No markdown content found")
                ai_message = AIMessage(content="No markdown content found in your last message. Please try again.")
                self._notify_ai_message(ai_message, self.name)
                return Command(goto="__end__", update={"messages": [ai_message]})

            # Initialize presentation data
            presentation_data["presentation_title"] = presentation_title
            presentation_data["slides_data"] = slides_data
            
            # Extract markdown content between ```markdown tags
            markdown_blocks = content.split("```markdown")[1].split("```")[0].strip()
            save_text(markdown_blocks, self.__datastore_path, "markdown_blocks.txt", copy=False)
            slides = markdown_blocks.split("###")

            # Process each slide
            for slide_number, slide in enumerate(slides):
                if "Slide" not in slide:
                    continue
                
                slide = slide.strip()
                logger.debug(f"Slide {slide_number}: {slide}")
                # Extract template slide URI if present
                template_slide_uri = None
                if "TemplateSlideUri:" in slide:
                    template_slide_uri = slide.split("TemplateSlideUri:")[1].split("\n")[0].strip()

                if template_slide_uri is None:
                    logger.debug(f"❌ No template slide URI found in slide content {slide}")
                    ai_message = AIMessage(content=f"No template slide URI found in slide content {slide}. Please try again.")
                    self._notify_ai_message(ai_message, self.name)
                    return Command(goto="__end__", update={"messages": [ai_message]})

                # Get shapes from template slide
                template_slide_number = int(template_slide_uri.split("ppt:Slide")[1])
                template_shapes = self.__powerpoint_integration.get_shapes_from_slide(template_slide_number)
                try:
                    shapes = extract_json_from_completion(self.convert_markdown_to_shapes(slide, template_shapes))
                    logger.debug(f"Shapes for slide {slide_number}: {json.dumps(shapes, indent=4)}")
                except Exception as e:
                    logger.error(f"❌ Failed to convert markdown to shapes for slide {slide_number}: {str(e)}")
                    shapes = []
                # Extract sources section if present
                sources = []
                if "Sources:" in slide:
                    sources_section = slide.split("Sources:")[1].strip()
                    # Split on newlines, filter empty strings and remove leading dash
                    sources = [s.strip().lstrip('-') for s in sources_section.split("\n") if s.strip()]
                logger.debug(f"Sources for slide {slide_number}: {sources}")

                # Parse slide data and add to slides_data list
                slide_data = {
                    "slide_number": slide_number,
                    "template_slide_number": template_slide_number,
                    "shapes": shapes,
                    "sources": sources
                }
                slides_data.append(slide_data)

            presentation_data["slides_data"] = slides_data

        save_json(presentation_data, self.__datastore_path, "presentation_data.json", copy=False)
        return Command(goto="convert_json_to_ppt", update={"presentation_data": presentation_data})
    
    def convert_json_to_ppt(
        self, 
        state: PowerPointState
    ) -> Command:
        """
        This node converts the JSON slide data into an actual PowerPoint presentation.
        It uses the PowerPointIntegration to create and populate the presentation.
        """
        from io import BytesIO
        from src.utils.Storage import save_powerpoint_presentation

        logger.debug("📊 Converting JSON to Powerpoint")

        # Get presentation data
        presentation_data = state.get("presentation_data", {})
        slides_data = presentation_data.get("slides_data", [])
        presentation_name = presentation_data.get("presentation_title", "Presentation").replace(" ", "") + ".pptx"
        
        # Create presentation from template
        presentation = self.__powerpoint_integration.create_presentation()

        # Clear existing slides and create new ones based on template
        presentation = self.__powerpoint_integration.remove_all_slides(presentation)

        # Create slides based on the data
        for slide_data in slides_data:
            # Duplicate template slide
            template_slide_number = slide_data.get("template_slide_number")
            presentation, new_slide_idx = self.__powerpoint_integration.duplicate_slide(self.__presentation, template_slide_number, presentation)

            # Add shapes to slide
            for shape in slide_data.get("shapes"):
                shape_id = shape.get("shape_id")
                text = shape.get("text")
                try:
                    presentation = self.__powerpoint_integration.update_shape(presentation, new_slide_idx, shape_id, text)
                except Exception as e:
                    logger.error(f"❌ Failed to update shape {shape_id} on slide {new_slide_idx}: {str(e)}")
                    continue

            sources = slide_data.get("sources")
            try:
                presentation = self.__powerpoint_integration.update_notes(presentation, new_slide_idx, sources)
            except Exception as e:
                logger.error(f"❌ Failed to update notes on slide {new_slide_idx}: {str(e)}")
                continue

        # Save presentation to storage
        save_powerpoint_presentation(presentation, self.__datastore_path, presentation_name, copy=False)

        # Save presentation to byte stream
        byte_stream = BytesIO() 
        presentation.save(byte_stream)
        byte_stream.seek(0)

        # Create asset in Naas
        asset = self.__naas_integration.upload_asset(
            data=byte_stream.getvalue(),  # Use the original turtle string
            workspace_id=self.__workspace_id,
            storage_name=self.__storage_name,
            prefix="assets",
            object_name=presentation_name,
            visibility="public",
            return_url=True
        )
        download_url = asset.get("asset_url")
        if not download_url:
            logger.error("❌ Failed to create asset in Naas.")
            ai_message = AIMessage(content=f"Presentation created successfully in: {self.__datastore_path}/{presentation_name}, but failed to create asset in Naas.")
        else:
            ai_message = AIMessage(content=f"✨ Your presentation has been successfully created!\n\n📎 Download link: [{presentation_name}]({download_url})\n\nLet me know if you need any changes or have questions about the presentation.")
        self._notify_ai_message(ai_message, self.name)
        return Command(goto="__end__", update={"messages": [ai_message]})
