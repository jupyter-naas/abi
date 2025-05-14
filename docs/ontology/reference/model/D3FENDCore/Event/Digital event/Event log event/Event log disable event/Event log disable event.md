# Event log disable event

## Overview

### Definition
An event indicating that the event logging service has been disabled, preventing it from collecting or recording logs.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#EventLogDisableEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#EventLogDisableEvent(Event<br>log<br>disable<br>event):::d3fend-->d3fend.owl#EventLogEvent
    d3fend.owl#EventLogEvent(Event<br>log<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Event log event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Event%20log%20event/Event%20log%20event.md)
- [Event log disable event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Event%20log%20event/Event%20log%20disable%20event/Event%20log%20disable%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
