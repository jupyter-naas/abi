# System call event

## Overview

### Definition
An event where a user-space process requests a service or resource from the operating system kernel through a system call interface, enabling controlled interactions with hardware or kernel-level operations.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#SystemCallEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#SystemCallEvent(System<br>call<br>event):::d3fend-->d3fend.owl#KernelEvent
    d3fend.owl#KernelEvent(Kernel<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Kernel event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Kernel%20event/Kernel%20event.md)
- [System call event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Kernel%20event/System%20call%20event/System%20call%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
