# Windows registry value deletion event

## Overview

### Definition
An event where a registry value is deleted from the Windows Registry, permanently removing its associated data.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#WindowsRegistryValueDeletionEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#WindowsRegistryValueDeletionEvent(Windows<br>registry<br>value<br>deletion<br>event):::d3fend-->d3fend.owl#WindowsRegistryValueEvent
    d3fend.owl#WindowsRegistryValueEvent(Windows<br>registry<br>value<br>event):::d3fend-->d3fend.owl#WindowsRegistryEvent
    d3fend.owl#WindowsRegistryEvent(Windows<br>registry<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Windows registry event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Windows%20registry%20event/Windows%20registry%20event.md)
- [Windows registry value event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Windows%20registry%20event/Windows%20registry%20value%20event/Windows%20registry%20value%20event.md)
- [Windows registry value deletion event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Windows%20registry%20event/Windows%20registry%20value%20event/Windows%20registry%20value%20deletion%20event/Windows%20registry%20value%20deletion%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
