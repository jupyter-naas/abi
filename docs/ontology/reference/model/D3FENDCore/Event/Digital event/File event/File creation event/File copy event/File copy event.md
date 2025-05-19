# File copy event

## Overview

### Definition
An event where a file is duplicated, creating a new file in a different location or under a different name while preserving the original file's content and attributes.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#FileCopyEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#FileCopyEvent(File<br>copy<br>event):::d3fend-->d3fend.owl#FileCreationEvent
    d3fend.owl#FileCreationEvent(File<br>creation<br>event):::d3fend-->d3fend.owl#FileEvent
    d3fend.owl#FileEvent(File<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [File event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/File%20event/File%20event.md)
- [File creation event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/File%20event/File%20creation%20event/File%20creation%20event.md)
- [File copy event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/File%20event/File%20creation%20event/File%20copy%20event/File%20copy%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
