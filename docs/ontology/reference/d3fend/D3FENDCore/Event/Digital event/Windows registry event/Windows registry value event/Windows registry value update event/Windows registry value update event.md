# Windows registry value update event

## Overview

### Definition
An event indicating changes to the data or configuration of an existing registry value within the Windows Registry.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#WindowsRegistryValueUpdateEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#WindowsRegistryValueUpdateEvent(Windows<br>registry<br>value<br>update<br>event):::d3fend-->d3fend.owl#WindowsRegistryValueEvent
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
- [Windows registry value update event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Windows%20registry%20event/Windows%20registry%20value%20event/Windows%20registry%20value%20update%20event/Windows%20registry%20value%20update%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
