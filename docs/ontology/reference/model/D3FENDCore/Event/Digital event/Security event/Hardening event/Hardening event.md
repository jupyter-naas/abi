# Hardening event

## Overview

### Definition
An event involving actions to strengthen defenses, such as applying patches or implementing secure configurations, reducing attack surfaces, and increasing the difficulty of exploitation by adversaries.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#HardeningEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#HardeningEvent(Hardening<br>event):::d3fend-->d3fend.owl#SecurityEvent
    d3fend.owl#SecurityEvent(Security<br>event):::d3fend-->d3fend.owl#DigitalEvent
    d3fend.owl#DigitalEvent(Digital<br>event):::d3fend-->d3fend.owl#Event
    d3fend.owl#Event(Event):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Event](/docs/ontology/reference/model/D3FENDCore/Event/Event.md)
- [Digital event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Digital%20event.md)
- [Security event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Security%20event/Security%20event.md)
- [Hardening event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Security%20event/Hardening%20event/Hardening%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
