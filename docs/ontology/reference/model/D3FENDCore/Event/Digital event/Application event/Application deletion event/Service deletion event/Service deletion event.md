# Service deletion event

## Overview

### Definition
An event capturing the uninstallation or deregistration of a service application, ensuring it is no longer operational or available to clients.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#ServiceDeletionEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#ServiceDeletionEvent(Service<br>deletion<br>event):::d3fend-->d3fend.owl#ApplicationDeletionEvent
    d3fend.owl#ApplicationDeletionEvent(Application<br>deletion<br>event):::d3fend-->d3fend.owl#ApplicationEvent
    d3fend.owl#ApplicationEvent(Application<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Application event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Application%20event/Application%20event.md)
- [Application deletion event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Application%20event/Application%20deletion%20event/Application%20deletion%20event.md)
- [Service deletion event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Application%20event/Application%20deletion%20event/Service%20deletion%20event/Service%20deletion%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
