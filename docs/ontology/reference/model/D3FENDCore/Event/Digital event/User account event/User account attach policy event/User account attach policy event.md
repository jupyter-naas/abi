# User account attach policy event

## Overview

### Definition
An event where an IAM policy is attached to a user account.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#UserAccountAttachPolicyEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#UserAccountAttachPolicyEvent(User<br>account<br>attach<br>policy<br>event):::d3fend-->d3fend.owl#UserAccountEvent
    d3fend.owl#UserAccountEvent(User<br>account<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [User account event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/User%20account%20event/User%20account%20event.md)
- [User account attach policy event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/User%20account%20event/User%20account%20attach%20policy%20event/User%20account%20attach%20policy%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
