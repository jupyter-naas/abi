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

### 3. Required Sections
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

### Claude Module
- **Focus**: Constitutional AI principles
- **Pattern**: Safety-first approach with reasoning
- **Workflow**: Input Analysis → Constitutional Check → Reasoning → Safety Validation → Response

### Gemini Module
- **Focus**: Multimodal understanding and reasoning
- **Pattern**: Cross-modal reasoning and generation
- **Workflow**: Multimodal Analysis → Reasoning → Generation → Validation

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

This modular approach ensures maintainability, scalability, and clear separation of concerns while maintaining ontological rigor and consistency across the entire ABI system.
