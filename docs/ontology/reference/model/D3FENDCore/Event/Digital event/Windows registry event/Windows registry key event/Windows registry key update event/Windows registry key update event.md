# Windows registry key update event

## Overview

### Definition
An event where an existing registry key is updated or reconfigured, reflecting changes to its metadata or properties.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#WindowsRegistryKeyUpdateEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#WindowsRegistryKeyUpdateEvent(Windows<br>registry<br>key<br>update<br>event):::d3fend-->d3fend.owl#WindowsRegistryKeyEvent
    d3fend.owl#WindowsRegistryKeyEvent(Windows<br>registry<br>key<br>event):::d3fend-->d3fend.owl#WindowsRegistryEvent
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
- [Windows registry key event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Windows%20registry%20event/Windows%20registry%20key%20event/Windows%20registry%20key%20event.md)
- [Windows registry key update event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Windows%20registry%20event/Windows%20registry%20key%20event/Windows%20registry%20key%20update%20event/Windows%20registry%20key%20update%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
