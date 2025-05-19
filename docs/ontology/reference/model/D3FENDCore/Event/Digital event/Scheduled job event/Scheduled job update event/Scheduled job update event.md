# Scheduled job update event

## Overview

### Definition
An event where an existing scheduled task is updated, altering parameters such as timing, conditions, or actions.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#ScheduledJobUpdateEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#ScheduledJobUpdateEvent(Scheduled<br>job<br>update<br>event):::d3fend-->d3fend.owl#ScheduledJobEvent
    d3fend.owl#ScheduledJobEvent(Scheduled<br>job<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Scheduled job event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Scheduled%20job%20event/Scheduled%20job%20event.md)
- [Scheduled job update event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Scheduled%20job%20event/Scheduled%20job%20update%20event/Scheduled%20job%20update%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
