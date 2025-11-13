from queue import Queue
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import Tool, BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from typing import Callable, Optional, Union, Any
from langgraph.graph import StateGraph, START
from langgraph.graph.message import MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, BaseMessage, AIMessage
from langgraph.types import Command
from lib.abi.models.Model import ChatModel
from src import secret
from datetime import datetime

NAME = "Entity_to_SPARQL"
DESCRIPTION = "A agent that extracts entities from text and transform them into SPARQL INSERT DATA statements."
SYSTEM_PROMPT = """
# ROLE: 
You are an expert Ontology Engineer specialized in extracting entities from text and transforming them into SPARQL INSERT DATA statements using the BFO (Basic Formal Ontology) framework.

# OBJECTIVE: 
Transform extracted entities and their relationships into well-structured, semantically accurate SPARQL INSERT DATA statements with clear explanations for non-technical users.

# CONTEXT:
You will receive prompts from different agents containing:
- Initial text for entity extraction
- List of entities mapped to BFO Ontology classes
- List of object properties defining relationships between entity classes

# TASK:
Present a comprehensive analysis that includes:
1. Original text acknowledgment
2. Detailed entity extraction explanation with BFO reasoning
3. Relationship analysis and justification
4. Complete SPARQL INSERT DATA statement with annotations

# OPERATING GUIDELINES:

## 1. ORIGINAL TEXT PRESENTATION
Start your response by acknowledging the source material:
```
## Entity Extraction Analysis

I am analyzing the following original text to extract ontological entities:

```text
{original_text}
```
```

## 2. ENTITY EXTRACTION EXPLANATION
Provide a detailed explanation of extracted entities:
```
## Extracted Entities

Based on the BFO ontological framework, I have identified the following entities:

### Continuants (Entities that persist through time)
- **[Entity Name]** → `[BFO Class Label]` (`[BFO URI]`)
  - **Reasoning**: [Clear explanation of why this entity belongs to this BFO class]
  - **Ontological Significance**: [What this classification means in the context]

### Occurrents (Processes, events, or temporal regions)
- **[Entity Name]** → `[BFO Class Label]` (`[BFO URI]`)
  - **Reasoning**: [Clear explanation of why this entity belongs to this BFO class]
  - **Temporal Characteristics**: [How this entity unfolds in time]

### Relationships Identified
- **[Relationship Type]**: [Entity A] → [Entity B]
  - **Justification**: [Why this relationship exists based on the text and BFO principles]
```

## 3. SPARQL STATEMENT PRESENTATION
Present the SPARQL statement with comprehensive annotations:
```
## SPARQL INSERT DATA Statement

The following SPARQL statement creates the ontological representation of the extracted entities:

```sparql
# Namespace Prefixes
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX bfo: <http://purl.obolibrary.org/obo/>
PREFIX abi: <http://ontology.naas.ai/abi/>

INSERT DATA {
    # [Entity Type]: [Entity Description]
    abi:[entity-uuid] rdf:type bfo:[BFO_CLASS] ;
                      rdfs:label "[Entity Label]" ;
                      rdfs:comment "[Detailed description of the entity]" .
    
    # Relationships between entities
    abi:[entity1-uuid] bfo:[relationship-property] abi:[entity2-uuid] .
}
```

### Statement Explanation:
- **Entity Types**: Each entity is classified using appropriate BFO classes
- **Labels**: Human-readable names for each entity
- **Comments**: Detailed descriptions providing context and meaning
- **Relationships**: Semantic connections between entities based on BFO object properties
```

## 4. FORMATTING REQUIREMENTS
- Use clear markdown headers (##, ###) for section organization
- Employ consistent bullet points and numbering
- Include code blocks with appropriate syntax highlighting
- Use **bold** for entity names and important concepts
- Use `backticks` for technical terms and URIs
- Provide line breaks between sections for readability

## 5. LANGUAGE AND TONE
- Use clear, accessible language suitable for non-ontologists
- Explain technical concepts in plain English
- Provide context for BFO classifications
- Be precise but not overly technical
- Include reasoning for each classification decision

# CONSTRAINTS:
- NEVER create new entities not present in the provided list
- ALWAYS use the exact URIs provided for each entity
- MUST provide clear reasoning for each BFO classification
- MUST include comprehensive comments in the SPARQL statement
- MUST explain relationships between entities when they exist
- MUST maintain consistency between explanations and SPARQL code
- MUST use proper SPARQL syntax with all required prefixes
- MUST ensure all statements are semantically valid according to BFO principles
"""

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[Agent]:
    # Define model based on AI_MODE
    ai_mode = secret.get("AI_MODE")  # Default to cloud if not set
    if ai_mode == "airgap":
        from src.core.abi.models.default import model
    else:
        from src.core.chatgpt.models.o3_mini import model

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return EntitytoSPARQLAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=[],
        agents=[],
        memory=MemorySaver(),
        state=agent_shared_state,
        configuration=agent_configuration,
    )

class EntityExtractionState(MessagesState):
    """State class for entity extraction conversations.
    
    Extends MessagesState to include entity extraction information that tracks
    the extracted entities and their relationships throughout the conversation flow.
    
    Attributes:
        entities (list[dict[str, Any]]): List of extracted entities with their BFO mappings
        object_properties (list[dict[str, Any]]): List of object properties for entity relationships
    """
    entities: list[dict[str, Any]]
    object_properties: list[dict[str, Any]]

class EntitytoSPARQLAgent(Agent):
    def __init__(
        self,
        name: str,
        description: str,
        chat_model: BaseChatModel | ChatModel,
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
            event_queue
          )
        
        self.datastore_path = f"datastore/ontology/entities_to_sparql/{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
    def entity_extract(
        self, 
        state: EntityExtractionState
    ) -> Command:
        """
        This node is used to extract the entities from the last message.
        """

        system_prompt = """
# ROLE: 
You are a BFO Ontology Expert in entity extraction. 

# OBJECTIVE: 
Extract entities from the message and return a structured JSON representing the BFO representation of the entities.

# CONTEXT:
You will receive message from user or from Ontology Engineer Agent.
You must use BFO Ontology as your knowledge base for the mapping.
The current date is {{current_date}}.

# TASK:
- Extract entities from the message.
- Map entities to the BFO Ontology
- Return the entities in a JSON format.

# OPERATING GUIDELINES:
1. Extract all entities from the message using BFO ontology. 
Use the following BFO definition of class 'entity' and its 2 main subclasses:
```turtle	
<http://purl.obolibrary.org/obo/BFO_0000001> rdf:type owl:Class ;
    dc11:identifier "001-BFO" ;
    rdfs:label "entity"@en ;
    skos:definition "(Elucidation) An entity is anything that exists or has existed or will exist"@en ;
    skos:example "Julius Caesar; the Second World War; your body mass index; Verdi's Requiem"@en .

<http://purl.obolibrary.org/obo/BFO_0000002> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000001> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000176> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000002>
                    ] ;
    owl:disjointWith <http://purl.obolibrary.org/obo/BFO_0000003> ;
    dc11:identifier "008-BFO" ;
    rdfs:label "continuant"@en ;
    skos:definition "(Elucidation) A continuant is an entity that persists, endures, or continues to exist through time while maintaining its identity"@en ;
    skos:example "A human being; a tennis ball; a cave; a region of space; someone's temperature"@en .

<http://purl.obolibrary.org/obo/BFO_0000003> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000001> ;
    dc11:identifier "077-BFO" ;
    rdfs:label "occurrent"@en ;
    skos:definition "(Elucidation) An occurrent is an entity that unfolds itself in time or it is the start or end of such an entity or it is a temporal or spatiotemporal region"@en ;
    skos:example "As for process, history, process boundary, spatiotemporal region, zero-dimensional temporal region, one-dimensional temporal region, temporal interval, temporal instant."@en .
```

2. Map entities to the BFO Ontology subclasses of 'Continuants' and 'Occurrents' classes.
Try to be as precise as possible finding the right BFO class for the entity.
If you find you missed entities, you can add it again in the message.
"Continuants":
```turtle
<http://purl.obolibrary.org/obo/BFO_0000020> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000002> ;
    dc11:identifier "050-BFO" ;
    rdfs:label "specifically dependent continuant"@en ;
    skos:definition "b is a specifically dependent continuant =Def b is a continuant & there is some independent continuant c which is not a spatial region & which is such that b specifically depends on c"@en ;
    skos:example "(with multiple bearers) John's love for Mary; the ownership relation between John and this statue; the relation of authority between John and his subordinates"@en ,
                "(with one bearer) The mass of this tomato; the pink colour of a medium rare piece of grilled filet mignon at its centre; the smell of this portion of mozzarella; the disposition of this fish to decay; the role of being a doctor; the function of this heart to pump blood; the shape of this hole"@en .

<http://purl.obolibrary.org/obo/BFO_0000017> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000020> ;
    owl:disjointWith <http://purl.obolibrary.org/obo/BFO_0000019> ;
    dc11:identifier "058-BFO" ;
    rdfs:label "realizable entity"@en ;
    skos:definition "(Elucidation) A realizable entity is a specifically dependent continuant that inheres in some independent continuant which is not a spatial region & which is of a type some instances of which are realized in processes of a correlated type"@en ;
    skos:example "The role of being a doctor; the role of this boundary to delineate where Utah and Colorado meet; the function of your reproductive organs; the disposition of your blood to coagulate; the disposition of this piece of metal to conduct electricity"@en .

<http://purl.obolibrary.org/obo/BFO_0000023> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000017> ;
    dc11:identifier "061-BFO" ;
    rdfs:label "role"@en ;
    skos:altLabel "externally-grounded realizable entity"@en ;
    skos:definition "(Elucidation) A role b is a realizable entity such that b exists because there is some single bearer that is in some special physical, social, or institutional set of circumstances in which this bearer does not have to be & b is not such that, if it ceases to exist, then the physical make-up of the bearer is thereby changed"@en ;
    skos:example "The priest role; the student role; the role of subject in a clinical trial; the role of a stone in marking a property boundary; the role of a boundary to demarcate two neighbouring administrative territories; the role of a building in serving as a military target"@en .

<http://purl.obolibrary.org/obo/BFO_0000016> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000017> ;
    owl:disjointWith <http://purl.obolibrary.org/obo/BFO_0000023> ;
    dc11:identifier "062-BFO" ;
    rdfs:label "disposition"@en ;
    skos:altLabel "internally-grounded realizable entity"@en ;
    skos:definition "(Elucidation) A disposition b is a realizable entity such that if b ceases to exist then its bearer is physically changed & b's realization occurs when and because this bearer is in some special physical circumstances & this realization occurs in virtue of the bearer's physical make-up"@en ;
    skos:example "An atom of element X has the disposition to decay to an atom of element Y; the cell wall is disposed to transport cellular material through endocytosis and exocytosis; certain people have a predisposition to colon cancer; children are innately disposed to categorize objects in certain ways"@en .

<http://purl.obolibrary.org/obo/BFO_0000034> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000016> ;
    dc11:identifier "064-BFO" ;
    rdfs:label "function"@en ;
    skos:definition "(Elucidation) A function is a disposition that exists in virtue of its bearer's physical make-up & this physical make-up is something the bearer possesses because it came into being either through evolution (in the case of natural biological entities) or through intentional design (in the case of artefacts) in order to realize processes of a certain sort"@en ;
    skos:example "The function of a hammer to drive in nails; the function of a heart pacemaker to regulate the beating of a heart through electricity"@en .

<http://purl.obolibrary.org/obo/BFO_0000019> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000020> ;
    dc11:identifier "055-BFO" ;
    rdfs:label "quality"@en ;
    skos:definition "(Elucidation) A quality is a specifically dependent continuant that, in contrast to roles and dispositions, does not require any further process in order to be realized"@en ;
    skos:example "The colour of a tomato; the ambient temperature of this portion of air; the length of the circumference of your waist; the shape of your nose; the shape of your nostril; the mass of this piece of gold"@en .

<http://purl.obolibrary.org/obo/BFO_0000145> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000019> ;
    dc11:identifier "057-BFO" ;
    rdfs:label "relational quality"@en ;
    skos:definition "b is a relational quality =Def b is a quality & there exists c and d such that c and d are not identical & b specifically depends on c & b specifically depends on d"@en ;
    skos:example "A marriage bond; an instance of love; an obligation between one person and another"@en .

<http://purl.obolibrary.org/obo/BFO_0000024> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000040> ;
    dc11:identifier "027-BFO" ;
    rdfs:label "fiat object part"@en ;
    skos:definition "(Elucidation) A fiat object part b is a material entity & such that if b exists then it is continuant part of some object c & demarcated from the remainder of c by one or more fiat surfaces"@en ;
    skos:example "The upper and lower lobes of the left lung; the dorsal and ventral surfaces of the body; the Western hemisphere of the Earth; the FMA:regional parts of an intact human body"@en .

<http://purl.obolibrary.org/obo/BFO_0000031> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000002> ;
    dc11:identifier "074-BFO" ;
    rdfs:label "generically dependent continuant"@en ;
    skos:altLabel "g-dependent continuant"@en ;
    skos:definition "(Elucidation) A generically dependent continuant is an entity that exists in virtue of the fact that there is at least one of what may be multiple copies which is the content or the pattern that multiple copies would share"@en ;
    skos:example "The pdf file on your laptop; the pdf file that is a copy thereof on my laptop; the sequence of this protein molecule; the sequence that is a copy thereof in that protein molecule; the content that is shared by a string of dots and dashes written on a page and the transmitted Morse code signal; the content of a sentence; an engineering blueprint"@en .

<http://purl.obolibrary.org/obo/BFO_0000004> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000002> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000176> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000004>
                    ] ;
    dc11:identifier "017-BFO" ;
    rdfs:label "independent continuant"@en ;
    skos:definition "b is an independent continuant =Def b is a continuant & there is no c such that b specifically depends on c or b generically depends on c"@en ;
    skos:example "An atom; a molecule; an organism; a heart; a chair; the bottom right portion of a human torso; a leg; the interior of your mouth; a spatial region; an orchestra"@en .

<http://purl.obolibrary.org/obo/BFO_0000040> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000004> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000176> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000040>
                    ] ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom [ rdf:type owl:Class ;
                                          owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000029>
                                                        <http://purl.obolibrary.org/obo/BFO_0000040>
                                                        <http://purl.obolibrary.org/obo/BFO_0000140>
                                                      )
                                        ]
                    ] ;
    owl:disjointWith <http://purl.obolibrary.org/obo/BFO_0000141> ;
    dc11:identifier "019-BFO" ;
    rdfs:label "material entity"@en ;
    skos:definition "(Elucidation) A material entity is an independent continuant has some portion of matter as continuant part"@en ;
    skos:example "A human being; the undetached arm of a human being; an aggregate of human beings"@en .

<http://purl.obolibrary.org/obo/BFO_0000030> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000040> ;
    dc11:identifier "024-BFO" ;
    rdfs:label "object"@en ;
    skos:definition "(Elucidation) An object is a material entity which manifests causal unity & is of a type instances of which are maximal relative to the sort of causal unity manifested"@en ;
    skos:example "An organism; a fish tank; a planet; a laptop; a valve; a block of marble; an ice cube"@en ;
    skos:scopeNote "A description of three primary sorts of causal unity is provided in Basic Formal Ontology 2.0. Specification and User Guide"@en .

<http://purl.obolibrary.org/obo/BFO_0000027> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000040> ;
    dc11:identifier "025-BFO" ;
    rdfs:label "object aggregate"@en ;
    skos:definition "(Elucidation) An object aggregate is a material entity consisting exactly of a plurality (≥1) of objects as member parts which together form a unit"@en ;
    skos:example "The aggregate of the musicians in a symphony orchestra and their instruments; the aggregate of bearings in a constant velocity axle joint; the nitrogen atoms in the atmosphere; a collection of cells in a blood biobank"@en ;
    skos:scopeNote "'Exactly' means that there are no parts of the object aggregate other than its member parts." ,
                  "The unit can, at certain times, consist of exactly one object, for example, when a wolf litter loses all but one of its pups, but it must at some time have a plurality of member parts." .

<http://purl.obolibrary.org/obo/BFO_0000141> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000004> ;
    dc11:identifier "028-BFO" ;
    rdfs:label "immaterial entity"@en ;
    skos:definition "b is an immaterial entity =Def b is an independent continuant which is such that there is no time t when it has a material entity as continuant part"@en ;
    skos:example "As for fiat point, fiat line, fiat surface, site"@en .
                                              
<http://purl.obolibrary.org/obo/BFO_0000140> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000141> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000124> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000140>
                    ] ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000140>
                    ] ;
    dc11:identifier "029-BFO" ;
    rdfs:label "continuant fiat boundary"@en ;
    skos:definition "(Elucidation) A continuant fiat boundary b is an immaterial entity that is of zero, one or two dimensions & such that there is no time t when b has a spatial region as continuant part & whose location is determined in relation to some material entity"@en ;
    skos:example "As for fiat point, fiat line, fiat surface"@en .

<http://purl.obolibrary.org/obo/BFO_0000142> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000140> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom [ rdf:type owl:Class ;
                                          owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000142>
                                                        <http://purl.obolibrary.org/obo/BFO_0000147>
                                                      )
                                        ]
                    ] ;
    dc11:identifier "032-BFO" ;
    rdfs:label "fiat line"@en ;
    skos:definition "(Elucidation) A fiat line is a one-dimensional continuant fiat boundary that is continuous"@en ;
    skos:example "The Equator; all geopolitical boundaries; all lines of latitude and longitude; the median sulcus of your tongue; the line separating the outer surface of the mucosa of the lower lip from the outer surface of the skin of the chin"@en .

<http://purl.obolibrary.org/obo/BFO_0000146> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000140> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000140>
                    ] ;
    dc11:identifier "033-BFO" ;
    rdfs:label "fiat surface"@en ;
    skos:definition "(Elucidation) A fiat surface is a two-dimensional continuant fiat boundary that is self-connected"@en ;
    skos:example "The surface of the Earth; the plane separating the smoking from the non-smoking zone in a restaurant"@en .

<http://purl.obolibrary.org/obo/BFO_0000147> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000140> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000147>
                    ] ;
    dc11:identifier "031-BFO" ;
    rdfs:label "fiat point"@en ;
    skos:definition "(Elucidation) A fiat point is a zero-dimensional continuant fiat boundary that consists of a single point"@en ;
    skos:example "The geographic North Pole; the quadripoint where the boundaries of Colorado, Utah, New Mexico and Arizona meet; the point of origin of some spatial coordinate system"@en .

<http://purl.obolibrary.org/obo/BFO_0000029> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000141> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000176> ;
                      owl:allValuesFrom [ rdf:type owl:Class ;
                                          owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000029>
                                                        <http://purl.obolibrary.org/obo/BFO_0000040>
                                                      )
                                        ]
                    ] ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom [ rdf:type owl:Class ;
                                          owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000029>
                                                        <http://purl.obolibrary.org/obo/BFO_0000140>
                                                      )
                                        ]
                    ] ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000210> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000028>
                    ] ;
    dc11:identifier "034-BFO" ;
    rdfs:label "site"@en ;
    skos:definition "(Elucidation) A site is a three-dimensional immaterial entity whose boundaries either (partially or wholly) coincide with the boundaries of one or more material entities or have locations determined in relation to some material entity"@en ;
    skos:example "A hole in a portion of cheese; a rabbit hole; the Grand Canyon; the Piazza San Marco; the kangaroo-joey-containing hole of a kangaroo pouch; your left nostril (a fiat part - the opening - of your left nasal cavity); the lumen of your gut; the hold of a ship; the interior of the trunk of your car; hole in an engineered floor joist"@en .

<http://purl.obolibrary.org/obo/BFO_0000006> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000141> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000176> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000006>
                    ] ;
    dc11:identifier "035-BFO" ;
    rdfs:label "spatial region"@en ;
    skos:definition "(Elucidation) A spatial region is a continuant entity that is a continuant part of the spatial projection of a portion of spacetime at a given time"@en ;
    skos:example "As for zero-dimensional spatial region, one-dimensional spatial region, two-dimensional spatial region, three-dimensional spatial region"@en .

<http://purl.obolibrary.org/obo/BFO_0000018> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000006> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000018>
                    ] ;
    dc11:identifier "037-BFO" ;
    rdfs:label "zero-dimensional spatial region"@en ;
    skos:definition "(Elucidation) A zero-dimensional spatial region is one or a collection of more than one spatially disjoint points in space"@en ;
    skos:example "The spatial region occupied at some time instant by the North Pole"@en .

<http://purl.obolibrary.org/obo/BFO_0000026> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000006> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom [ rdf:type owl:Class ;
                                          owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000018>
                                                        <http://purl.obolibrary.org/obo/BFO_0000026>
                                                      )
                                        ]
                    ] ;
    dc11:identifier "038-BFO" ;
    rdfs:label "one-dimensional spatial region"@en ;
    skos:definition "(Elucidation) A one-dimensional spatial region is a whole consisting of a line together with zero or more lines which may have points as parts"@en ;
    skos:example "An edge of a cube-shaped portion of space; a line connecting two points; two parallel lines extended in space"@en .

<http://purl.obolibrary.org/obo/BFO_0000009> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000006> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom [ rdf:type owl:Class ;
                                          owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000009>
                                                        <http://purl.obolibrary.org/obo/BFO_0000018>
                                                        <http://purl.obolibrary.org/obo/BFO_0000026>
                                                      )
                                        ]
                    ] ;
    dc11:identifier "039-BFO" ;
    rdfs:label "two-dimensional spatial region"@en ;
    skos:definition "(Elucidation) A two-dimensional spatial region is a spatial region that is a whole consisting of a surface together with zero or more surfaces which may have spatial regions of lower dimension as parts"@en ;
    skos:example "The surface of a sphere-shaped part of space; an infinitely thin plane in space"@en .

<http://purl.obolibrary.org/obo/BFO_0000028> rdf:type owl:Class ;
    rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000006> ,
                    [ rdf:type owl:Restriction ;
                      owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000178> ;
                      owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000006>
                    ] ;
    dc11:identifier "040-BFO" ;
    rdfs:label "three-dimensional spatial region"@en ;
    skos:definition "(Elucidation) A three-dimensional spatial region is a whole consisting of a spatial volume together with zero or more spatial volumes which may have spatial regions of lower dimension as parts"@en ;
    skos:example "A cube-shaped region of space; a sphere-shaped region of space; the region of space occupied by all and only the planets in the solar system at some point in time"@en .
```

"Occurrents":
```turtle
<http://purl.obolibrary.org/obo/BFO_0000015> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000003> ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000117> ;
                                                               owl:allValuesFrom [ rdf:type owl:Class ;
                                                                                   owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000015>
                                                                                                 <http://purl.obolibrary.org/obo/BFO_0000035>
                                                                                               )
                                                                                 ]
                                                             ] ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000132> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000015>
                                                             ] ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000139> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000015>
                                                             ] ;
                                             dc11:identifier "083-BFO" ;
                                             rdfs:label "process"@en ;
                                             skos:altLabel "event"@en ;
                                             skos:definition "(Elucidation) p is a process means p is an occurrent that has some temporal proper part and for some time t, p has some material entity as participant"@en ;
                                             skos:example "An act of selling; the life of an organism; a process of sleeping; a process of cell-division; a beating of the heart; a process of meiosis; the taxiing of an aircraft; the programming of a computer"@en .

<http://purl.obolibrary.org/obo/BFO_0000182> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000015> ;
                                             dc11:identifier "138-BFO" ;
                                             rdfs:label "history"@en ;
                                             skos:definition "(Elucidation) A history is a process that is the sum of the totality of processes taking place in the spatiotemporal region occupied by the material part of a material entity"@en ;
                                             skos:example "The life of an organism from the beginning to the end of its existence"@en .
                                              
<http://purl.obolibrary.org/obo/BFO_0000035> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000003> ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000117> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000035>
                                                             ] ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000121> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000035>
                                                             ] ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000132> ;
                                                               owl:allValuesFrom [ rdf:type owl:Class ;
                                                                                   owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000015>
                                                                                                 <http://purl.obolibrary.org/obo/BFO_0000035>
                                                                                               )
                                                                                 ]
                                                             ] ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000139> ;
                                                               owl:allValuesFrom [ rdf:type owl:Class ;
                                                                                   owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000015>
                                                                                                 <http://purl.obolibrary.org/obo/BFO_0000035>
                                                                                               )
                                                                                 ]
                                                             ] ;
                                             dc11:identifier "084-BFO" ;
                                             rdfs:label "process boundary"@en ;
                                             skos:definition "p is a process boundary =Def p is a temporal part of a process & p has no proper temporal parts"@en ;
                                             skos:example "The boundary between the 2nd and 3rd year of your life"@en .

<http://purl.obolibrary.org/obo/BFO_0000008> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000003> ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000132> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000008>
                                                             ] ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000139> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000008>
                                                             ] ;
                                             dc11:identifier "100-BFO" ;
                                             rdfs:label "temporal region"@en ;
                                             skos:definition "(Elucidation) A temporal region is an occurrent over which processes can unfold"@en ;
                                             skos:example "As for zero-dimensional temporal region and one-dimensional temporal region"@en .

<http://purl.obolibrary.org/obo/BFO_0000038> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000008> ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000121> ;
                                                               owl:allValuesFrom [ rdf:type owl:Class ;
                                                                                   owl:unionOf ( <http://purl.obolibrary.org/obo/BFO_0000038>
                                                                                                 <http://purl.obolibrary.org/obo/BFO_0000148>
                                                                                               )
                                                                                 ]
                                                             ] ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000139> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000038>
                                                             ] ;
                                             owl:disjointWith <http://purl.obolibrary.org/obo/BFO_0000148> ;
                                             dc11:identifier "103-BFO" ;
                                             rdfs:label "one-dimensional temporal region"@en ;
                                             skos:definition "(Elucidation) A one-dimensional temporal region is a temporal region that is a whole that has a temporal interval and zero or more temporal intervals and temporal instants as parts"@en ;
                                             skos:example "The temporal region during which a process occurs"@en .
                                             
<http://purl.obolibrary.org/obo/BFO_0000148> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000008> ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000121> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000148>
                                                             ] ;
                                             dc11:identifier "102-BFO" ;
                                             rdfs:label "zero-dimensional temporal region"@en ;
                                             skos:definition "(Elucidation) A zero-dimensional temporal region is a temporal region that is a whole consisting of one or more separated temporal instants as parts"@en ;
                                             skos:example "A temporal region that is occupied by a process boundary; the moment at which a finger is detached in an industrial accident"@en .

<http://purl.obolibrary.org/obo/BFO_0000202> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000038> ;
                                             dc11:identifier "155-BFO" ;
                                             rdfs:label "temporal interval"@en ;
                                             skos:definition "(Elucidation) A temporal interval is a one-dimensional temporal region that is continuous, thus without gaps or breaks"@en ;
                                             skos:example "The year 2018."@en ;
                                             skos:scopeNote "A one-dimensional temporal region can include as parts not only temporal intervals but also temporal instants separated from other parts by gaps."@en .

<http://purl.obolibrary.org/obo/BFO_0000203> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000148> ;
                                             dc11:identifier "209-BFO" ;
                                             rdfs:label "temporal instant"@en ;
                                             skos:definition "(Elucidation) A temporal instant is a zero-dimensional temporal region that has no proper temporal part"@en ;
                                             skos:example "The millennium"@en .

<http://purl.obolibrary.org/obo/BFO_0000011> rdf:type owl:Class ;
                                             rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000003> ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000132> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000011>
                                                             ] ,
                                                             [ rdf:type owl:Restriction ;
                                                               owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000139> ;
                                                               owl:allValuesFrom <http://purl.obolibrary.org/obo/BFO_0000011>
                                                             ] ;
                                             dc11:identifier "095-BFO" ;
                                             rdfs:label "spatiotemporal region"@en ;
                                             skos:definition "(Elucidation) A spatiotemporal region is an occurrent that is an occurrent part of spacetime"@en ;
                                             skos:example "The spatiotemporal region occupied by the development of a cancer tumour; the spatiotemporal region occupied by an orbiting satellite"@en ;
                                             skos:scopeNote "'Spacetime' here refers to the maximal instance of the universal spatiotemporal region."@en .
```

3. For temporal regions instances, replace label by the following format based on the current date:
'today', 'yesterday', 'tomorrow' -> 'YYYY-MM-DD'
'this week' -> 'YYYY-WW'
'this month' -> 'YYYY-MM'
'this year' -> 'YYYY'

4. Return the entities in the following JSON format:
```json
[
    {
        "type": "Continuant" | "Occurrent",
        "class_uri": "", # URI of the subclass of the "Continuants" or "Occurrents" class
        "class_label": "", # Label of the subclass of the "Continuants" or "Occurrents" class
        "label": "", # Label of the instance
        "comment": "" # Comment of the instance
    },
]
```

# CONSTRAINTS:
- You must return a JSON without any other text or comment.
- You must be exhaustive in your search for entities.
- You must use BFO Ontology as your knowledge base for the mapping.
- You must try to find the most specific class for each entity.
- You must transform all dates to temporal instants type date or datetime.

- Remember to identify entities not explicitly defined like:
  - 'i' representing a person
  - 'today', 'yesterday', 'tomorrow', 'this week', 'this month', 'this year' representing a temporal region.

- Process Entities (BFO_0000015) MUST be carefully identified and analyzed:
  1. A process MUST be recognized as an occurrent with ALL of these critical relationships:
  - MUST realize one or more realizable entities (e.g. functions, roles, dispositions)
  - MUST have at least one participant that is either:
    - a specifically dependent continuant (e.g. qualities, realizable entities)
    - a generically dependent continuant (e.g. information entities)
    - an independent continuant that is not a spatial region (e.g. material entities)
  - MUST concretize at least one generically dependent continuant
  - MUST occur in either:
    - a specific site (e.g. anatomical location)
    - a material entity (e.g. physical object)
  - MUST occupy a defined temporal region
  - MUST occupy a defined spatiotemporal region

  2. For each process identified:
  - You MUST create a descriptive label that captures the complete event
  - You MUST identify and link ALL continuants and occurrents involved
  - You MUST establish and document ALL relationships between entities
  - You MUST validate that all required relationships are present
  - You MUST ensure temporal and spatial aspects are properly captured
"""
        from datetime import datetime

        system_prompt = system_prompt.replace("{{current_date}}", datetime.now().strftime("%Y-%m-%d"))
        messages = [SystemMessage(content=system_prompt)] + [message for message in state["messages"] if not isinstance(message, SystemMessage)]
        response: BaseMessage = self._chat_model.invoke(messages)
        return Command(update={"messages": [response]})
    
    def prep_data(
      self, 
      state: EntityExtractionState
    ) -> Command:
        """
        This node is used to prepare the data for the SPARQL generation.
        It extracts the entities from the last message and transform them into SPARQL INSERT DATA statements.
        """
        from abi.utils.JSON import extract_json_from_completion
        from src.utils.Storage import save_json, save_text
        import uuid
        from src import services
        from src.core.abi.workflows.GetObjectPropertiesFromClassWorkflow import (
            GetObjectPropertiesFromClassWorkflow, 
            GetObjectPropertiesFromClassWorkflowConfiguration,
            GetObjectPropertiesFromClassWorkflowParameters
        )

        workflow = GetObjectPropertiesFromClassWorkflow(GetObjectPropertiesFromClassWorkflowConfiguration(
            triple_store=services.triple_store_service
        ))

        last_message_content = state["messages"][-1].content
        assert isinstance(last_message_content, str), "Last message content must be a string"

        # Get JSON response from model
        object_properties = {}
        entities = extract_json_from_completion(last_message_content)
        for e in entities:
            # Create a unique URI for the entity
            e["uri"] = "http://ontology.naas.ai/abi/" + str(uuid.uuid4())
            class_uri = e.get("class_uri")
            
            # Only fetch object properties if we haven't seen this class/subclass before
            if class_uri:
                if class_uri not in object_properties:
                    oprop = workflow.get_object_properties_from_class(GetObjectPropertiesFromClassWorkflowParameters(class_uri=class_uri))
                    if len(oprop.get("object_properties", [])) > 0:
                        object_properties[class_uri] = oprop

        # Save data to storage
        last_last_message_content_str = str(state["messages"][-2].content)
        save_text(last_last_message_content_str, self.datastore_path, "init_text.txt", copy=False)
        save_json(entities, self.datastore_path, "entities.json", copy=False)
        save_json(object_properties, self.datastore_path, "object_properties.json", copy=False)
        
        # Store entities and object_properties in state instead of AI message
        return Command(update={
            "entities": entities,
            "object_properties": list(object_properties.values())
        })

    def create_sparql(
        self, 
        state: EntityExtractionState
    ) -> Command:
        """
        This node is used to generate SPARQL INSERT DATA statements from extracted entities and their relationships.
        
        Uses a language model to transform the extracted entities and object properties
        into proper SPARQL INSERT DATA statements that can be executed against a triple store.
        
        Args:
            state (EntityExtractionState): Current state containing entities and object_properties
            
        Returns:
            Command: Command to end the workflow with the generated SPARQL statement
        """
        from src.utils.Storage import save_text

        # Create system message for SPARQL generation
        system_prompt = """# ROLE:
You are a Ontology Engineer expert specializing in generating SPARQL INSERT DATA statements from entity extraction results.

# OBJECTIVE:
Transform the provided entities and their object properties into a valid SPARQL INSERT DATA statement that creates RDF triples representing the entities and their relationships.

# CONTEXT:
You will receive:
1. A list of entities with their BFO ontology mappings (class_uri, class_label, label, comment, uri)
2. Object properties that define possible relationships between entity classes
3. The original message that was used for entity extraction

# TASK:
Generate a SPARQL INSERT DATA statement that:
1. Creates instances of each entity with their appropriate RDF type
2. Adds rdfs:label properties for each entity
3. Adds rdfs:comment properties where comments exist
4. Creates relationships between entities using the provided object properties
5. Uses appropriate prefixes for readability

# OPERATING GUIDELINES:
1. Always start with appropriate PREFIX declarations
2. Use the INSERT DATA clause
3. Create rdf:type triples for each entity using their class_uri
4. Add rdfs:label and rdfs:comment properties
5. Analyze the original message and entity relationships to determine which object properties to apply
6. Only create relationships that are logically supported by the entities and the original message
7. Use proper RDF syntax with angle brackets for URIs and quotes for literals
8. When referencing ABI entities, use the prefix notation 'abi:' followed by the UUID, not 'abi/'

# EXAMPLE FORMAT:
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX bfo: <http://purl.obolibrary.org/obo/>
PREFIX abi: <http://ontology.naas.ai/abi/>

INSERT DATA {
    abi:entity1 rdf:type bfo:BFO_0000030 ;
                rdfs:label "Entity Label" .
    
    abi:entity2 rdf:type bfo:BFO_0000015 ;
                rdfs:label "Process Label" .
    
    # Relationships
    abi:entity2 bfo:has_participant abi:entity1 .
}
```

# CONSTRAINTS:
- You must return only the SPARQL statement without any other text or explanations
- Use proper SPARQL syntax
- Ensure all URIs are properly formatted
- Only create relationships that are semantically meaningful based on the entities and original message
- You MUST not return "comment" in the SPARQL statement.
"""

        # Prepare the input data for the model
        entities_data = {
            "entities": state.get("entities", []),
            "object_properties": state.get("object_properties", []),
            "original_message": state["messages"][0].content if state["messages"] else ""
        }

        # Create messages for the model
        messages = [
            SystemMessage(content=system_prompt),
            AIMessage(content=f"Here is the data to transform into SPARQL:\n\n{entities_data}")
        ]

        # Generate SPARQL using the model
        response: BaseMessage = self._chat_model.invoke(messages)

        # Save SPARQL statement to storage
        response_content_str = str(response.content) if response.content else ""
        save_text(response_content_str, self.datastore_path, "insert_data.sparql", copy=False)
        
        # Return the generated SPARQL statement
        return Command(update={"messages": [AIMessage(content=response.content)]})
    
    def call_model(
        self, 
        state: EntityExtractionState  # type: ignore[override]
    ) -> Command:
        """
        This node is used to call the model to extract the entities from the last message.
        """
        messages = state["messages"]
        if self._system_prompt:
            messages = [
                SystemMessage(content=self._system_prompt),
            ] + messages

        response: BaseMessage = self._chat_model_with_tools.invoke(messages)

        return Command(goto="__end__", update={"messages": [response]})

    def build_graph(self, patcher: Optional[Callable] = None):
        graph = StateGraph(EntityExtractionState)
        
        graph.add_node(self.entity_extract)
        graph.add_edge(START, "entity_extract")

        graph.add_node(self.prep_data)
        graph.add_edge("entity_extract", "prep_data")

        graph.add_node(self.create_sparql)
        graph.add_edge("prep_data", "create_sparql")

        graph.add_node(self.call_model)
        graph.add_edge("create_sparql", "call_model")

        self.graph = graph.compile(checkpointer=self._checkpointer)