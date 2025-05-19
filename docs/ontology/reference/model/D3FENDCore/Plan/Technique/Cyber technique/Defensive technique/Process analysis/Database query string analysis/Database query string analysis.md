# Database query string analysis

## Overview

### Definition
Analyzing database queries to detect [SQL Injection](https://capec.mitre.org/data/definitions/66.html).

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#DatabaseQueryStringAnalysis

### Subclass Of
```mermaid
graph BT
    d3fend.owl#DatabaseQueryStringAnalysis(Database<br>query<br>string<br>analysis):::d3fend-->d3fend.owl#ProcessAnalysis
    d3fend.owl#ProcessAnalysis(Process<br>analysis):::d3fend-->d3fend.owl#DefensiveTechnique
    d3fend.owl#DefensiveTechnique(Defensive<br>technique):::d3fend-->d3fend.owl#CyberTechnique
    d3fend.owl#CyberTechnique(Cyber<br>technique):::d3fend-->d3fend.owl#Technique
    d3fend.owl#Technique(Technique):::d3fend-->d3fend.owl#Plan
    d3fend.owl#Plan(Plan):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Plan](/docs/ontology/reference/model/D3FENDCore/Plan/Plan.md)
- [Technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Technique.md)
- [Cyber technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Cyber%20technique.md)
- [Defensive technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Defensive%20technique.md)
- [Process analysis](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Process%20analysis/Process%20analysis.md)
- [Database query string analysis](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Process%20analysis/Database%20query%20string%20analysis/Database%20query%20string%20analysis.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
