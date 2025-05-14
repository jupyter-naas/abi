# Add user to group event

## Overview

### Definition
An event where a user is added to a group, granting the user the permissions and privileges associated with the group.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#AddUserToGroupEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#AddUserToGroupEvent(Add<br>user<br>to<br>group<br>event):::d3fend-->d3fend.owl#GroupManagementEvent
    d3fend.owl#GroupManagementEvent(Group<br>management<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Group management event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Group%20management%20event/Group%20management%20event.md)
- [Add user to group event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Group%20management%20event/Add%20user%20to%20group%20event/Add%20user%20to%20group%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
