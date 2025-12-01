import os
from datetime import datetime
from queue import Queue
from typing import Any, Callable, Optional, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import BaseTool, Tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.types import Command
from naas_abi_core import logger
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.powerpoint import ABIModule
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipelineConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflow,
    CreatePresentationFromTemplateWorkflowConfiguration,
    CreatePresentationFromTemplateWorkflowParameters,
)

NAME = "PowerPoint"
DESCRIPTION = "An agent specialized in creating PowerPoint presentations."
AVATAR_URL = "https://static.vecteezy.com/system/resources/thumbnails/017/396/831/small/microsoft-power-point-mobile-apps-logo-free-png.png"
SYSTEM_PROMPT = """
<role>
You are PowerPoint, an agent that converts a user brief into a fully structured PowerPoint presentation using slides structure from template. 
You never invent facts; you structure, adapt, and clearly label content from the brief. 
</role>

<objective>
Create a clear, audience-aligned presentation that:
- Uses the template's structure as a guide
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
- Search presentation in knowledge graph if it already exists.
</tasks>

<tools>
[TOOLS]
</tools>

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

- Populate each slides with detailed content and template slide to use with 'shape_alt_text' guidance if provided and return result in markdown format. 
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
) -> Agent:
    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools
    tools: list = []
    # from naas_abi_core.modules.templatablesparqlquery import get_tools
    # templates_tools = [
    #     "powerpoint_search_presentation_by_name",
    #     "powerpoint_get_slide_by_uri",
    #     "powerpoint_get_shape_by_uri",
    #     "powerpoint_get_all_text_content_by_presentation",
    # ]
    # tools += get_tools(templates_tools)

    # Set configuration
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=system_prompt)

    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    # Set default datastore and template paths
    datastore_path = "datastore/powerpoint/presentations"
    template_path = (
        "src/marketplace/applications/powerpoint/templates/TemplateNaasPPT.pptx"
    )
    module: ABIModule = ABIModule.get_instance()
    workspace_id = module.configuration.workspace_id
    storage_name = module.configuration.storage_name
    return PowerPointAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        datastore_path=datastore_path,
        template_path=template_path,
        workspace_id=workspace_id,
        storage_name=storage_name,
        tools=tools,
        memory=MemorySaver(),
        state=agent_shared_state,
        configuration=agent_configuration,
    )


class PowerPointAgent(Agent):
    def __init__(
        self,
        name: str,
        description: str,
        chat_model: BaseChatModel | ChatModel,
        datastore_path: str,
        template_path: str,
        workspace_id: str,
        storage_name: str,
        tools: list[Union[Tool, BaseTool, "Agent"]] = [],
        agents: list["Agent"] = [],
        memory: BaseCheckpointSaver = MemorySaver(),
        state: AgentSharedState = AgentSharedState(),
        configuration: AgentConfiguration = AgentConfiguration(),
        event_queue: Queue | None = None,
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
            event_queue,
        )
        self.__template_path = template_path
        self.__template_name: str = (
            os.path.basename(self.__template_path).lower().replace(".pptx", "")
            if self.__template_path
            else "TemplatePresentation"
        )
        self.__datastore_path: str = os.path.join(
            datastore_path,
            self.__template_name,
            datetime.now().strftime("%Y%m%d%H%M%S"),
        )
        self.__workspace_id: str = workspace_id
        self.__storage_name: str = storage_name
        self.__powerpoint_configuration = PowerPointIntegrationConfiguration(
            template_path=self.__template_path
        )
        self.__powerpoint_integration = PowerPointIntegration(
            self.__powerpoint_configuration
        )
        self.__triple_store_service = (
            ABIModule.get_instance().engine.services.triple_store
        )
        self.__powerpoint_pipeline_configuration = (
            AddPowerPointPresentationPipelineConfiguration(
                powerpoint_configuration=self.__powerpoint_configuration,
                triple_store=ABIModule.get_instance().engine.services.triple_store,
            )
        )
        self.__naas_configuration = NaasIntegrationConfiguration(
            api_key=ABIModule.get_instance().configuration.naas_api_key
        )

        self.__create_presentation_from_template_workflow = (
            CreatePresentationFromTemplateWorkflow(
                CreatePresentationFromTemplateWorkflowConfiguration(
                    triple_store=ABIModule.get_instance().engine.services.triple_store,
                    powerpoint_configuration=self.__powerpoint_configuration,
                    naas_configuration=self.__naas_configuration,
                    pipeline_configuration=self.__powerpoint_pipeline_configuration,
                    datastore_path=self.__datastore_path,
                    workspace_id=self.__workspace_id,
                    storage_name=self.__storage_name,
                )
            )
        )

    def build_graph(self, patcher: Optional[Callable] = None):
        graph = StateGraph(PowerPointState)

        graph.add_node(self.current_active_agent)
        graph.add_edge(START, "current_active_agent")

        graph.add_node(self.continue_conversation)

        graph.add_node(self.inject_template_structure)

        graph.add_node(self.validate_presentation_draft)

        graph.add_node(self.call_model)

        graph.add_node(self.call_tools)

        graph.add_node(self.convert_markdown_to_json)

        graph.add_node(self.convert_json_to_ppt)

        self.graph = graph.compile(checkpointer=self._checkpointer)

    def continue_conversation(self, state: MessagesState) -> Command:
        """
        This node continues the conversation by injecting the template structure into the system prompt.
        """
        return Command(goto="inject_template_structure")

    def inject_template_structure(self, state: PowerPointState) -> Command:
        """
        This node injects the template structure into the system prompt.
        """
        from naas_abi_core.utils.Graph import ABI
        from rdflib import Graph
        from rdflib.namespace import OWL, RDF, RDFS, XSD, Namespace
        from rdflib.term import Literal, URIRef

        # import uuid

        if "[TEMPLATE_STRUCTURE]" in self._system_prompt:
            logger.debug("🔧 Injecting template structure")
            # Create graph
            ABI = Namespace("http://ontology.naas.ai/abi/")
            PPT = Namespace("http://ontology.naas.ai/abi/powerpoint/")
            graph = Graph()
            graph.bind("ppt", PPT)
            graph.bind("abi", ABI)

            # Add presentation triples
            ppt_class = URIRef("http://ontology.naas.ai/abi/powerpoint/Presentation")
            # presentation_uri = ABI[str(uuid.uuid4())]
            presentation_uri = ABI[
                Literal(self.__template_name.lower().replace(" ", ""))
            ]
            graph.add((presentation_uri, RDF.type, OWL.NamedIndividual))
            graph.add((presentation_uri, RDF.type, ppt_class))
            graph.add((presentation_uri, RDFS.label, Literal(self.__template_name)))

            # Get all shapes and slides from template
            all_shapes_and_slides = (
                self.__powerpoint_integration.get_all_shapes_and_slides()
            )
            for slide in all_shapes_and_slides:
                slide_number = slide.get("slide_number")
                shapes = slide.get("shapes", [])
                # slide_uri = ABI[str(uuid.uuid4())]
                slide_uri = ABI[Literal(f"Slide{slide_number}")]

                # Add slide triples
                graph.add((slide_uri, RDF.type, OWL.NamedIndividual))
                graph.add((slide_uri, RDF.type, ppt_class))
                # graph.add((slide_uri, RDFS.label, Literal(f"Slide {slide_number}")))
                graph.add(
                    (
                        slide_uri,
                        PPT.slide_number,
                        Literal(slide_number, datatype=XSD.integer),
                    )
                )
                graph.add((presentation_uri, PPT.hasSlide, slide_uri))
                graph.add((slide_uri, PPT.isSlideOf, presentation_uri))

                # Add shapes triples
                for shape in shapes:
                    shape_id = shape.get("shape_id")
                    shape_type = shape.get("shape_type")
                    shape_text = shape.get("text")
                    shape_alt_text = shape.get("shape_alt_text")
                    if shape_type not in [14, 17] and shape_text == "":
                        continue

                    # shape_uri = ABI[str(uuid.uuid4())]
                    shape_uri = ABI[Literal(f"Shape{slide_number}_{shape_id}")]
                    graph.add((shape_uri, RDF.type, OWL.NamedIndividual))
                    graph.add((shape_uri, RDF.type, ppt_class))
                    # graph.add((shape_uri, RDFS.label, Literal(shape_text)))
                    graph.add(
                        (
                            shape_uri,
                            PPT.shape_id,
                            Literal(shape_id, datatype=XSD.integer),
                        )
                    )
                    graph.add(
                        (
                            shape_uri,
                            PPT.shape_type,
                            Literal(shape_type, datatype=XSD.integer),
                        )
                    )
                    graph.add((shape_uri, PPT.shape_alt_text, Literal(shape_alt_text)))
                    graph.add((shape_uri, PPT.shape_text, Literal(shape_text)))
                    graph.add((shape_uri, PPT.isShapeOf, slide_uri))
                    graph.add((slide_uri, PPT.hasShape, shape_uri))

            turtle = f"""
            ```turtle
            {graph.serialize(format="turtle")}
            ```
            """
            system_prompt = self._system_prompt.replace("[TEMPLATE_STRUCTURE]", turtle)
            self.set_system_prompt(system_prompt)
        return Command(goto="validate_presentation_draft")

    def validate_presentation_draft(self, state: PowerPointState) -> Command:
        """
        This node validates the presentation draft.
        """
        import pydash as _

        logger.debug("🔍 Validating presentation draft")

        # Get last messages
        last_human_message = self.get_last_human_message(state)
        last_ai_message: Any | None = _.find(
            state["messages"][::-1], lambda m: isinstance(m, AIMessage)
        )

        if (
            last_human_message
            and last_ai_message
            and "```markdown" in last_ai_message.content
        ):
            # Create validation prompt
            messages: list[BaseMessage] = [
                SystemMessage(
                    content=f"""
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
    """
                )
            ]

            # Get validation response
            response = self._chat_model.invoke(messages)

            if response.content == "true":
                logger.debug(
                    f"✅ Reponse content '{response.content}'. Going to convert markdown to JSON."
                )
                return Command(goto="convert_markdown_to_json")
            else:
                logger.debug(
                    f"❌ Reponse content '{response.content}'. Going back to conversation."
                )
        return Command(goto="call_model")

    def convert_markdown_to_shapes(
        self, markdown_blocks: str, template_shapes: list[dict]
    ) -> str:
        """
        This function converts markdown slide structure to shapes format.
        It parses the markdown content and extracts shapes data from template JSON.
        """
        messages: list[BaseMessage] = [
            SystemMessage(
                content=f"""
You are a precise JSON transformer. Your task is to convert markdown content into a shapes-based JSON format.

Input:
1. Markdown blocks containing slide content
2. Template JSON showing the shape structure for each slide

Instructions:
1. Understand the shapes structure from template_json.
2. Map the text in markdown content to corresponding shape by updating the "text" field of the shape. 
    If unable to find a match but you have 'text' or 'shape_alt_text' with value, try to fill it with your knowledge of the content and shape or return empty string '" "'.
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
"""
            )
        ]
        # Get validation response
        response = self._chat_model.invoke(messages)
        return (
            response.content
            if hasattr(response, "content") and isinstance(response.content, str)
            else ""
        )

    def convert_markdown_to_json(self, state: PowerPointState) -> Command:
        """
        This node converts markdown slide structure to JSON format.
        It parses the markdown content from the last message and extracts slide data.
        """
        import json

        import pydash as _
        from naas_abi_core.utils.JSON import extract_json_from_completion
        from naas_abi_core.utils.Storage import save_json, save_text

        logger.debug("📝 Converting markdown to JSON")
        # Get last messages
        last_ai_message: Any | None = _.find(
            state["messages"][::-1], lambda m: isinstance(m, AIMessage)
        )

        # Initialize slides data list
        presentation_data: dict = {}
        slides_data: list = []

        if last_ai_message:
            # Extract presentation title
            content = last_ai_message.content
            if "**PresentationTitle:" in content:
                presentation_title = (
                    content.split("PresentationTitle:")[1].split("**")[0].strip()
                )
            else:
                logger.debug("❌ No presentation title found")
                presentation_title = "Presentation"

            # Extract markdown content between ```markdown tags
            if "```markdown" not in content:
                logger.debug("❌ No markdown content found")
                ai_message = AIMessage(
                    content="No markdown content found in your last message. Please try again."
                )
                self._notify_ai_message(ai_message, self.name)
                return Command(goto="__end__", update={"messages": [ai_message]})

            # Initialize presentation data
            presentation_data["presentation_title"] = presentation_title
            presentation_data["slides_data"] = slides_data

            # Extract markdown content between ```markdown tags
            markdown_blocks = content.split("```markdown")[1].split("```")[0].strip()
            save_text(
                markdown_blocks,
                self.__datastore_path,
                "markdown_blocks.txt",
                copy=False,
            )
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
                    template_slide_uri = (
                        slide.split("TemplateSlideUri:")[1].split("\n")[0].strip()
                    )

                if template_slide_uri is None:
                    logger.debug(
                        f"❌ No template slide URI found in slide content {slide}"
                    )
                    ai_message = AIMessage(
                        content=f"No template slide URI found in slide content {slide}. Please try again."
                    )
                    self._notify_ai_message(ai_message, self.name)
                    return Command(goto="__end__", update={"messages": [ai_message]})

                # Get shapes from template slide
                template_shapes: list = []
                try:
                    template_slide_number = int(
                        template_slide_uri.split("ppt:Slide")[1]
                    )
                    template_shapes = (
                        self.__powerpoint_integration.get_shapes_from_slide(
                            template_slide_number
                        )
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Failed to get shapes from template slide {template_slide_uri}: {str(e)}"
                    )

                if len(template_shapes) == 0:
                    continue

                shapes: list | dict = {}
                try:
                    shapes = extract_json_from_completion(
                        self.convert_markdown_to_shapes(slide, template_shapes)
                    )
                    logger.debug(
                        f"Shapes for slide {slide_number}: {json.dumps(shapes, indent=4)}"
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Failed to convert markdown to shapes for slide {slide_number}: {str(e)}"
                    )

                # Extract sources section if present
                sources: list = []
                if "Sources:" in slide:
                    sources_section = slide.split("Sources:")[1].strip()
                    # Split on newlines, filter empty strings and remove leading dash
                    sources = [
                        s.strip().lstrip("-").strip()
                        for s in sources_section.split("\n")
                        if s.strip()
                    ]
                logger.debug(f"Sources for slide {slide_number}: {sources}")

                # Parse slide data and add to slides_data list
                slide_data = {
                    "slide_number": slide_number,
                    "template_slide_number": template_slide_number,
                    "shapes": shapes,
                    "sources": sources,
                }
                slides_data.append(slide_data)

            presentation_data["slides_data"] = slides_data

        save_json(
            presentation_data,
            self.__datastore_path,
            "presentation_data.json",
            copy=False,
        )
        return Command(
            goto="convert_json_to_ppt", update={"presentation_data": presentation_data}
        )

    def convert_json_to_ppt(self, state: PowerPointState) -> Command:
        """
        This node converts the JSON slide data into an actual PowerPoint presentation.
        It uses the PowerPointIntegration to create and populate the presentation.
        """
        logger.debug("📊 Converting JSON to Powerpoint")

        # Get presentation data
        presentation_data = state.get("presentation_data", {})
        slides_data = presentation_data.get("slides_data", [])
        presentation_name = (
            presentation_data.get("presentation_title", "Presentation").replace(" ", "")
            + ".pptx"
        )

        # Create presentation from template
        presentation = (
            self.__create_presentation_from_template_workflow.create_presentation(
                CreatePresentationFromTemplateWorkflowParameters(
                    presentation_name=presentation_name,
                    slides_data=slides_data,
                    template_path=self.__template_path,
                )
            )
        )
        download_url = presentation.get("download_url")
        presentation_uri = presentation.get("presentation_uri")

        if not download_url:
            logger.warning("❌ Failed to download URL from Naas.")
            content = f"""
✨ Your presentation has been successfully created in: {self.__datastore_path}/{presentation_name} and added to your knowledge graph (URI: {presentation_uri});
But we were unable to download URL from Naas. Please contact your support team with the following information:

```markdown
## Bug Report
### Title: 
Failed to get download URL after presentation creation

### Description:
We were unable to get the download URL after creating the presentation:
- Presentation name: {presentation_name}
- Storage path: {self.__datastore_path}
- Presentation URI: {presentation_uri}

### Priority: 
High
```
"""
            ai_message = AIMessage(content=content)
        else:
            content = f"""
✨ Your presentation has been successfully created and added to your knowledge graph (URI: {presentation_uri})!
\nYou can access it with the following public download link: [{presentation_name}]({download_url})
\n\nPlease, let me know if you need to create another presentation.
"""
            ai_message = AIMessage(content=content)
        self._notify_ai_message(ai_message, self.name)
        return Command(goto="__end__", update={"messages": [ai_message]})

    def duplicate(
        self,
        queue: Queue | None = None,
        agent_shared_state: AgentSharedState | None = None,
    ) -> "Agent":
        """Create a new instance of the agent with the same configuration.

        This method creates a deep copy of the agent with the same configuration
        but with its own independent state. This is useful when you need to run
        multiple instances of the same agent concurrently.

        Returns:
            PowerPointAgent: A new PowerPointAgent instance with the same configuration
        """
        shared_state = agent_shared_state or AgentSharedState()

        if queue is None:
            queue = Queue()

        # We duplicated each agent and add them as tools.
        # This will be recursively done for each sub agents.
        agents: list["Agent"] = [
            agent.duplicate(queue, shared_state) for agent in self._original_agents
        ]

        new_agent = self.__class__(
            name=self._name,
            description=self._description,
            chat_model=self._chat_model,
            tools=self._original_tools,
            agents=agents,
            memory=self._checkpointer,
            state=shared_state,  # Create new state instance
            configuration=self._configuration,
            event_queue=queue,
            datastore_path=self.__datastore_path,
            template_path=self.__template_path,
        )

        return new_agent
