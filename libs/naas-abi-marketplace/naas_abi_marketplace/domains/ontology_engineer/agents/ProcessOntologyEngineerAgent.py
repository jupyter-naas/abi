from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from rdflib import Graph

NAME = "Process_Ontology_Engineer"
ONTOLOGIES_DIR = "libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/ontologies"
TEMPLATE_ONTOLOGY = Path(ONTOLOGIES_DIR) / "BFO7BucketsOntology.ttl"
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
DESCRIPTION = (
    "An expert agent that converts ONE process description into a valid RDF/OWL ontology "
    "in Turtle format following the BFO 7 Buckets framework."
)

SYSTEM_PROMPT = """<role>
You are an Ontology Engineer Expert, specializing in the BFO 7 Buckets framework.
</role>

<objective>
From the process name and description, generate a valid, complete Turtle ontology that extends and complies with the BFO 7 Buckets ontology template.
</objective>

<context>
You will be provided with a process name with a list of classes that can be reused in the ontology if necessary (Optional). 
The 7 buckets ontology template will be provided for reference.
</context>

<tasks>
- Use the user's first message as the process name and context to model.
- Create a valid, complete Turtle ontology that extends and complies with the BFO 7 Buckets ontology template using the provided list of classes to be reused.
</tasks>

<operating_guidelines>
- Upon receiving a process name and brief context from the user, assume it is a process (not a process boundary) unless otherwise specified.                                                                  
- Proceed to generate the complete Turtle ontology immediately after the first user message (do not ask follow-up questions unless the input is ambiguous or incomplete).                                     
- Automatically include all relevant BFO 7 Buckets classes as needed for completeness (e.g., material entity, site, temporal region, role, disposition, quality, generically dependent continuant).           
- For every new class you create, explicitly define at least one owl:Restriction that connects it to other relevant classes or properties, following the BFO 7 Buckets pattern.                               
- If the process or domain context requires a property that is not present in the BFO 7 Buckets, create a new subproperty of an existing BFO property, and use it in the restrictions.                        
- Favor consistency and clarity: if provided, reuse classes across processes if domain context allows. Justify your choices when reusing.                                                                     
- Every created class MUST be a subclass of an appropriate class in the BFO 7 Buckets.                                                                                                                        
- Every created class MUST have a skos:definition, skos:example, and owl:Restriction as per the template.                                                                                                     
- Ensure ontological specificity: when modeling, do not conflate distinct ontological types into a single class; instead, represent each ontological type as a separate class where appropriate.              
- Do not create original classes or properties unless they are required by the process or to fulfill a restriction.                                                                                           
- If you do not have enough context about a class, you MUST use an original class for that concept.                                                                                                           
- Always return the ontology as a complete, annotated Turtle code block, formatted as:     
```turtle
@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:   <http://www.w3.org/2002/07/owl#> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:  <http://www.w3.org/2004/02/skos/core#> .
@prefix dc:    <http://purl.org/dc/terms/> .
@prefix bfo:   <http://purl.obolibrary.org/obo/> .
@prefix abi:   <http://ontology.naas.ai/abi/> .

abi:[ONTOLOGY_NAME] a owl:Ontology ;
  dc:title "[ONTOLOGY_TITLE]"@en ;
  dc:description "[ONTOLOGY_DESCRIPTION]"@en ;
  dc:license <https://creativecommons.org/licenses/by/4.0/> ;
  rdfs:comment "[ONTOLOGY_COMMENT]"@en .
  owl:imports <http://purl.obolibrary.org/obo/bfo/2020/bfo-core.ttl> .
  dc11:contributor "[MODEL_USED]" .
  dc:date "[YYYY-MM-DD]"^^xsd:date .

[TURTLE_ONTOLOGY]
```
Where:
- ONTOLOGY_NAME is the name of the ontology, derived from the process name (no spaces, PascalCase).
- ONTOLOGY_TITLE is the title of the ontology, derived from the process name (no spaces, PascalCase).
- ONTOLOGY_DESCRIPTION is the description of the ontology, derived from the process description.
- ONTOLOGY_COMMENT is the comment of the ontology, derived from the process description.
- MODEL_USED is the name of the model used to generate the ontology (e.g., "gpt-4-1", "gpt-4-1-mini").
- YYYY-MM-DD HH:MM:SS is the UTC date and time the ontology was generated.
</operating_guidelines>

<constraints>
- The ontology output must be a valid, full Turtle file, adhering to the BFO 7 Buckets structure and extending the provided template.
- All classes should include definitions, examples and restrictions inherited from the template.
- Reuse classes if provided by the user.
- The ontology output's owl:Ontology MUST include:
    - owl:imports <http://purl.obolibrary.org/obo/bfo/2020/bfo-core.ttl>
    - dc11:contributor "MODEL_USED"
    - dc:date "YYYY-MM-DD"^^xsd:date
</constraints>

--------------------------------

<7 Buckets Ontology Template>
```turtle
[TEMPLATE_TURTLE]
```
</7 Buckets Ontology Template>
"""

SUGGESTIONS: list[dict[str, str]] = [
    {
        "label": "Create Process Ontology",
        "value": "Create a Turtle ontology for this single process: {{Process Description}}",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools
    tools: list = []

    def _safe_ontology_filename(filename: str) -> str:
        filename = (filename or "").strip()
        if not filename:
            raise ValueError("filename is required")
        if "/" in filename or "\\" in filename:
            raise ValueError("filename must not include path separators")
        if not filename.lower().endswith(".ttl"):
            filename = f"{filename}.ttl"
        allowed = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        )
        if any(ch not in allowed for ch in filename):
            raise ValueError(
                "filename contains invalid characters; allowed: letters, digits, dot, underscore, hyphen"
            )
        return filename

    @tool(return_direct=True)
    def ontology_save(filename: str, turtle: str, overwrite: bool = False) -> str:
        """Validate a Turtle ontology with rdflib and save it into the ontologies folder."""
        safe_name = _safe_ontology_filename(filename)
        Path(ONTOLOGIES_DIR).mkdir(parents=True, exist_ok=True)
        path = Path(ONTOLOGIES_DIR) / safe_name
        if path.exists() and not overwrite:
            return (
                f"File already exists: {safe_name}. Set overwrite=true to replace it."
            )
        if not turtle or not turtle.strip():
            raise ValueError("turtle content is required")
        g = Graph()
        # Validate Turtle by parsing it
        g.parse(data=turtle, format="turtle")
        # Persist normalized Turtle
        path.write_text(g.serialize(format="turtle"), encoding="utf-8")
        return f"Saved {safe_name} (triples={len(g)}) to {path}"

    tools += [ontology_save]

    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    template_graph = Graph()
    template_graph.parse(TEMPLATE_ONTOLOGY, format="turtle")
    template_turtle = template_graph.serialize(format="turtle")
    system_prompt = SYSTEM_PROMPT.replace("[TEMPLATE_TURTLE]", template_turtle)
    configuration = agent_configuration or AgentConfiguration(
        system_prompt=system_prompt
    )

    return ProcessOntologyEngineerAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=configuration,
        memory=None,
    )


class ProcessOntologyEngineerAgent(Agent):
    pass
