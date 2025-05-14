# Service stop event

## Overview

### Definition
An event capturing the cessation of a service application’s operations, transitioning it to an inactive state while ceasing its functionality to clients or dependent systems.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#ServiceStopEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#ServiceStopEvent(Service<br>stop<br>event):::d3fend-->d3fend.owl#ServiceEvent
    d3fend.owl#ServiceEvent(Service<br>event):::d3fend-->d3fend.owl#ApplicationEvent
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
- [Service event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Application%20event/Service%20event/Service%20event.md)
- [Service stop event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Application%20event/Service%20event/Service%20stop%20event/Service%20stop%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
