# Process termination event

## Overview

### Definition
An event marking the cessation of a process, including resource deallocation and cleanup, either due to normal completion or abnormal termination.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#ProcessTerminationEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#ProcessTerminationEvent(Process<br>termination<br>event):::d3fend-->d3fend.owl#ProcessEvent
    d3fend.owl#ProcessEvent(Process<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Process event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Process%20event/Process%20event.md)
- [Process termination event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Process%20event/Process%20termination%20event/Process%20termination%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
