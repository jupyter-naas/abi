# ABI Ontology

> [!WARNING]
> This folder and the documents in this folder are currently under development. Content may be incomplete or subject to change. Contact us if you have any question: support@naas.ai

This is the root folder for the **ABI Ontology**, a comprehensive universal ontology framework built on the Basic Formal Ontology (BFO). The ABI Ontology provides semantic models for representing entities, processes, and relationships across multiple domains of enterprise operations.

## Ontology Structure

The ABI Ontology is organized according to the following principles:

### Basic Formal Ontology (BFO) Foundation

All classes in the ABI Ontology are grounded in BFO's fundamental distinction between:

- **Continuants**: Entities that persist through time (e.g., organizations, roles, systems)
- **Occurrents**: Entities that unfold in time (e.g., processes, events, temporal regions)

```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000003(Occurrent):::BFO-->BFO_0000001
    
    BFO_0000004(Independent<br>Continuant):::BFO-->BFO_0000002
    BFO_0000020(Specifically Dependent<br>Continuant):::BFO-->BFO_0000002
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    BFO_0000040(Material<br>Entity):::BFO-->BFO_0000004
    BFO_0000141(Immaterial<br>Entity):::BFO-->BFO_0000004
    
    BFO_0000015(Process):::BFO-->BFO_0000003
    BFO_0000035(Process<br>Boundary):::BFO-->BFO_0000003
    BFO_0000008(Temporal<br>Region):::BFO-->BFO_0000003
    BFO_0000011(Spatiotemporal<br>Region):::BFO-->BFO_0000003
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

### Domain Foundries

The ontology is divided into domain-specific **Foundries**, each focusing on a particular aspect of enterprise operations:


- **Enterprise Management Foundry**: Core business operations, organizational structures, and management processes
- **Cyber Security Foundry**: Security agents, operations, threats, and protective measures

*Planned Foundries:*
- **ESG Foundry**: Environmental, Social, and Governance entities and processes
- **Data & Analytics Foundry**: Information assets, analytics processes, and data governance
- **Finance & Accounting Foundry**: Financial assets, transactions, and reporting processes

Each foundry maintains the same BFO-based structure of Continuants and Occurrents, but applies it to domain-specific concepts.

## Folder Organization

```
/docs/ontology/
├── foundries/                     # Domain-specific ontology modules (human-maintained)
│   ├── enterprise_management/     # Business operations and management
│   │   ├── Continuant/           # Persistent entities (orgs, roles, etc.)
│   │   └── Occurrent/            # Time-bound processes and events
│   │
│   ├── cyber_security/           # Security and protection domain
│   │   ├── Continuant/           # Security agents, assets, etc.
│   │   └── Occurent/             # Security processes, events, etc.
│   │
│   └── [other foundries]/        # Additional domain-specific modules
│
└── reference/                     # Auto-generated technical documentation from src codebase
    ├── model/                     # Generated ontology model and relationships
    └── ontologies/                 # Domain-specific ontologies by foundry
```

## Documentation Approach

The ABI Ontology documentation follows a dual approach:

1. **Foundry Documentation (Human-Maintained)**
   - Domain-specific ontology concepts organized by foundry
   - Human-readable explanations, examples, and usage guidance
   - Conceptual organization following BFO principles
   - Maintained manually by ontology engineers and domain experts

2. **Reference Documentation (Auto-Generated)**
   - Automatically generated from the ontology model in the `src` directory
   - Technical representation of ontology structures, mappings, and relationships
   - Links between BFO, CCO (Common Core Ontologies), and external standards
   - Reflects the actual implementation details of the ontology

## Key Principles

The ABI Ontology follows these design principles:

1. **BFO Conformance**: All classes properly align with BFO's distinctions and hierarchies
2. **Modularity**: Domain-specific concepts are organized into cohesive foundries
3. **Reusability**: Common patterns and classes are shared across foundries
4. **Clarity**: Clear definitions and examples for all ontological entities
5. **Practical Application**: Designed for real-world enterprise use cases

## Usage

This ontology can be used for:

- AI Management Systems 
- Enterprise architecture modeling
- Business process management
- Information integration
- Decision support systems
- Compliance and governance
- Knowledge representation and reasoning

## Ontology Classes

Each class in the ABI Ontology follows a standard documentation format:

- **Definition**: Precise description of the entity
- **BFO Hierarchy**: Position in the BFO class hierarchy
- **Properties**: Relevant object and data properties
- **Examples**: Real-world instances of the class

For specifics of each foundry, see the README files in their respective directories.
