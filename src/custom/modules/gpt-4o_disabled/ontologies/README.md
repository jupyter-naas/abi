# GPT-4o Message Ontology

This directory contains the RDF/OWL ontology definitions for the GPT-4o message formats and conversational structures. The ontology provides a semantic representation of conversations, messages, content items, and tool interactions within the GPT-4o module.

## Overview

The Message Ontology defines a formal vocabulary for representing GPT-4o conversations as semantic knowledge, linking it with the BFO (Basic Formal Ontology) upper ontology through IAO (Information Artifact Ontology) integration.

The ontology enables:
- Semantic representation of conversations and message flows
- Integration with knowledge graphs and inference engines
- Querying conversation content using SPARQL
- Formal verification and consistency checking using reasoners
- Interoperability with other semantic systems

## Files

- `MessageOntology.ttl` - The primary ontology definition in Turtle format with axioms
- `tools/` - Utilities for working with the ontology, including converters for transforming JSON to RDF

## Key Concepts

The ontology models these primary classes:

1. **Conversation**: A session of message exchanges
2. **Message**: Different types of messages including:
   - SystemMessage - Instructions or context from the system
   - UserMessage - Content from the user
   - AssistantMessage - Content from the GPT-4o model
   - ToolMessage - Responses from tools

3. **ContentItem**: Different media types in messages
4. **ToolCall**: Calls made to tools by the assistant
5. **Role**, **Interface**, and **ContentType**: Enumeration classes

## Formal Axioms

The ontology includes various formal axioms that enforce logical constraints and enable reasoning:

### Disjointness Axioms
- Role types (SystemRole, UserRole, AssistantRole, ToolRole) are mutually disjoint
- Message types (SystemMessage, UserMessage, AssistantMessage, ToolMessage) are mutually disjoint
- Content types (TextContent, ImageContent, AudioContent, VideoContent, FileContent) are mutually disjoint
- Interface types (StreamlitInterface, TerminalInterface, NaasWorkspaceInterface, ApiInterface) are mutually disjoint

### Property Characteristics
- Functional properties (messageId, conversationId, hasRole, etc.)
- Inverse properties (hasMessage/partOf)
- Special properties (precedesInConversation is transitive, irreflexive, and asymmetric)

### Class Completeness
- Complete enumeration of all types (Role, Message, Interface, ContentType)

### Cardinality Constraints
- Messages must have exactly one messageId, date, and role
- Content items must have exactly one content type
- Tool messages must respond to exactly one tool call
- Conversations must contain at least one message

### Content Type Requirements
- Text content must have at least one text value
- Image, audio, video, and file content must have at least one URL

## BFO Integration

The ontology integrates with the Basic Formal Ontology (BFO) via the Information Artifact Ontology (IAO):

- Messages are modeled as Information Content Entities (IAO:0000030)
- Content items represent Information Content
- Roles, interfaces, and content types are specialized Information Entities

## Usage

### Converting JSON Conversations to RDF

Use the converter tool to transform JSON message files into RDF:

```bash
# Convert a single file
python tools/converter.py path/to/message.json -f turtle

# Convert a directory of files
python tools/converter.py path/to/messages/dir -o path/to/output/dir -r -f turtle
```

### Querying the Knowledge Graph

Once conversations are converted to RDF, you can query them using SPARQL:

```sparql
# Example: Find all system messages in conversations
PREFIX msg: <https://w3id.org/abi/gpt-4o/schema/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?message ?content
WHERE {
  ?message rdf:type msg:SystemMessage .
  ?message msg:hasContent ?contentItem .
  ?contentItem msg:textContent ?content .
}
```

### Reasoning with the Ontology

The formal axioms enable automated reasoning with tools like HermiT, Pellet, or ELK:

```bash
# Check consistency using the OWL API and HermiT
java -jar owltools.jar --reasoner HermiT MessageOntology.ttl --check-consistency

# Run SWRL rules with Pellet
java -jar pellet.jar rules --input-format turtle MessageOntology.ttl rules.swrl
```

## Dependencies

- Python 3.7+
- RDFLib (`pip install rdflib`)
- Reasoners (optional): HermiT, Pellet, or ELK for advanced reasoning

## Integration with the Analytics Pipeline

This ontology forms the foundation of the analytics pipeline described in the module's README. The RDF data generated through this ontology is stored in a triplestore database and used to:

1. Track conversation patterns and topics
2. Generate network visualizations
3. Perform semantic analysis of interactions
4. Calculate usage metrics and trends

## Extending the Ontology

To extend the ontology for new capabilities:

1. Add new classes or properties to `MessageOntology.ttl`
2. Define appropriate axioms for new concepts to maintain logical consistency
3. Update the converter tool if needed to handle new data structures
4. Document the changes in this README

## Visualization

The ontology structure can be visualized using tools like:
- [WebVOWL](http://vowl.visualdataweb.org/webvowl.html)
- [Protégé](https://protege.stanford.edu/) with ontology visualization plugins 