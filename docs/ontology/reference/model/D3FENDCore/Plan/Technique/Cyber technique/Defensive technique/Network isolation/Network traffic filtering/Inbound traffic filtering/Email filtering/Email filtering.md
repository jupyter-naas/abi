# Email filtering

## Overview

### Definition
Filtering incoming email traffic based on specific criteria.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#EmailFiltering

### Subclass Of
```mermaid
graph BT
    d3fend.owl#EmailFiltering(Email<br>filtering):::d3fend-->d3fend.owl#InboundTrafficFiltering
    d3fend.owl#InboundTrafficFiltering(Inbound<br>traffic<br>filtering):::d3fend-->d3fend.owl#NetworkTrafficFiltering
    d3fend.owl#NetworkTrafficFiltering(Network<br>traffic<br>filtering):::d3fend-->d3fend.owl#NetworkIsolation
    d3fend.owl#NetworkIsolation(Network<br>isolation):::d3fend-->d3fend.owl#DefensiveTechnique
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
- [Network isolation](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Network%20isolation/Network%20isolation.md)
- [Network traffic filtering](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Network%20isolation/Network%20traffic%20filtering/Network%20traffic%20filtering.md)
- [Inbound traffic filtering](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Network%20isolation/Network%20traffic%20filtering/Inbound%20traffic%20filtering/Inbound%20traffic%20filtering.md)
- [Email filtering](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Network%20isolation/Network%20traffic%20filtering/Inbound%20traffic%20filtering/Email%20filtering/Email%20filtering.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
