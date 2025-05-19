# Access mediation event

## Overview

### Definition
An event involving the intermediary control mechanism that evaluates access requests and enforces access control decisions, ensuring that subjects' resource interactions comply with the established access policies.

### Examples
Not defined.

### Aliases
Access Enforcement Event

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#AccessMediationEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#AccessMediationEvent(Access<br>mediation<br>event):::d3fend-->d3fend.owl#AccessControlEvent
    d3fend.owl#AccessControlEvent(Access<br>control<br>event):::d3fend-->d3fend.owl#AuthorizationEvent
    d3fend.owl#AuthorizationEvent(Authorization<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Authorization event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Authorization%20event/Authorization%20event.md)
- [Access control event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Authorization%20event/Access%20control%20event/Access%20control%20event.md)
- [Access mediation event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Authorization%20event/Access%20control%20event/Access%20mediation%20event/Access%20mediation%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
