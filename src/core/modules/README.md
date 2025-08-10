# ABI Core Modules - Ontology Structure

This directory contains the core modules of the ABI system, each with its own ontology structure for modeling AI agents and systems.

## Modular Ontology Architecture

Each module follows a consistent ontology structure that mirrors the software architecture:

```
src/core/modules/
├── chatgpt/
│   ├── agents/
│   ├── integrations/
│   ├── models/
│   └── ontologies/
│       └── ChatGPTInstances.ttl
├── claude/
│   ├── agents/
│   ├── integrations/
│   ├── models/
│   └── ontologies/
│       └── ClaudeInstances.ttl
├── gemini/
│   ├── agents/
│   ├── integrations/
│   ├── models/
│   └── ontologies/
│       └── GeminiInstances.ttl
└── ontology/
    └── ontologies/
        └── domain-level/
            ├── AIAgentOntology.ttl
            └── AIAgentInstances.ttl
```

## Ontology File Naming Convention

- **Base Ontology**: `{ModuleName}Ontology.ttl` (e.g., `ChatGPTOntology.ttl`)
- **Instances**: `{ModuleName}Instances.ttl` (e.g., `ChatGPTInstances.ttl`)
- **Specialized**: `{ModuleName}{Specialization}.ttl` (e.g., `ChatGPTWorkflows.ttl`)

## Module-Specific Ontology Guidelines

### 1. Namespace Structure
Each module uses its own namespace:
- ChatGPT: `chatgpt: <http://ontology.naas.ai/abi/chatgpt/>`
- Claude: `claude: <http://ontology.naas.ai/abi/claude/>`
- Gemini: `gemini: <http://ontology.naas.ai/abi/gemini/>`

### 2. Import Structure
All module ontologies import the base AI Agent Ontology:
```turtle
<http://ontology.naas.ai/abi/{module}/{ModuleName}Instances> rdf:type owl:Ontology ;
    owl:imports <http://ontology.naas.ai/abi/AIAgentOntology> ;
    dc:title "{ModuleName} Module Instances" ;
    dc:description "Concrete instances demonstrating {ModuleName} AI agents with advanced relationships."@en .
```

### 3. Module Namespaces
Each module uses its own namespace:
- ChatGPT: `chatgpt: <http://ontology.naas.ai/abi/chatgpt/>`
- Claude: `claude: <http://ontology.naas.ai/abi/claude/>`
- Gemini: `gemini: <http://ontology.naas.ai/abi/gemini/>`
- Mistral: `mistral: <http://ontology.naas.ai/abi/mistral/>`

### 4. Required Sections
Each module ontology should include:

#### AI Systems
- Main system with subsystems
- Load balancer configuration
- System complexity classification

#### AI Agents
- Primary and fallback agents
- Specialized roles and collaboration priorities
- Agent collaboration relationships

#### Model Instances
- Specific model instances with qualities
- Performance metrics (accuracy, latency, token capacity)
- Provider information

#### Processes
- Temporal coordination workflows
- Process sequences and triggers
- Participant relationships

#### Qualities
- Model accuracy, latency, and capacity
- Performance measurements
- Quality constraints

#### Information Content
- Model specifications
- System documentation
- Configuration details

## Advanced Relationship Modeling

Each module should demonstrate:

### Agent Collaboration
```turtle
{module}:PrimaryAgent a abi:AIAgent ;
    abi:collaboratesWith {module}:SpecializedAgent ;
    abi:collaborationPriority "9" ;
    abi:hasFallbackAgent {module}:FallbackAgent .
```

### System Composition
```turtle
{module}:MainSystem a abi:AISystem ;
    abi:hasSubsystem {module}:Subsystem1, {module}:Subsystem2 ;
    abi:hasLoadBalancer {module}:LoadBalancer .
```

### Temporal Coordination
```turtle
{module}:Process1 a abi:TextGenerationProcess ;
    abi:temporalSequence "1" ;
    abi:triggersProcess {module}:Process2 .
```

## Module-Specific Patterns

### ChatGPT Module
- **Focus**: Multimodal capabilities (text + image)
- **Pattern**: Text generation + image generation collaboration
- **Workflow**: Preprocessing → Generation → Validation → Delivery
- **Instances**: 33 total (systems, agents, models, processes)

### Claude Module
- **Focus**: Constitutional AI principles
- **Pattern**: Safety-first approach with reasoning
- **Workflow**: Input Analysis → Constitutional Check → Reasoning → Safety Validation → Response
- **Instances**: 32 total (systems, agents, models, processes)

### Gemini Module
- **Focus**: Speed optimization and multimodal processing
- **Pattern**: Native image/video understanding with ultra-fast processing
- **Workflow**: Input Processing → Multimodal Analysis → Speed Optimization → Response Generation
- **Instances**: 31 total (systems, agents, models, processes)

### Mistral Module
- **Focus**: Technical excellence and European compliance
- **Pattern**: Code generation with GDPR compliance
- **Workflow**: Problem Analysis → Technical Solution → Code Generation → Compliance Validation → Documentation
- **Instances**: 33 total (systems, agents, models, processes)

## Best Practices

1. **Consistency**: Use the same structure across all modules
2. **Descriptive Comments**: Include `rdfs:comment` for all instances
3. **Realistic Data**: Use actual performance metrics and capabilities
4. **Modularity**: Keep module-specific concerns separate
5. **Reusability**: Import base ontology for common patterns
6. **Extensibility**: Design for future additions and modifications

## Validation

Each module ontology should be validated against:
- BFO 7 categories representation
- CCO Agent inheritance
- Advanced relationship axioms
- Data property constraints
- Business logic compliance

## Integration

Module ontologies integrate through:
- Shared base ontology (`AIAgentOntology.ttl`)
- Cross-module agent collaboration
- System composition relationships
- Temporal coordination workflows

## Current Status

- **Total Modules**: 4 (ChatGPT, Claude, Gemini, Mistral)
- **Total Instances**: 129 across all modules
- **Total Triples**: 1,189 in comprehensive test suite
- **Cross-Module Collaborations**: 15 identified relationships
- **Temporal Sequences**: 14 validated workflows
- **System Compositions**: 12 hierarchical structures

## Testing

Run the comprehensive test suite:
```bash
python run_ontology_tests.py
```

This validates all modules, cross-module relationships, and demonstrates real-world AI system complexity modeling.

This modular approach ensures maintainability, scalability, and clear separation of concerns while maintaining ontological rigor and consistency across the entire ABI system.
