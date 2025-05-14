# User account password reset event

## Overview

### Definition
An event where a user account's password is reset, typically due to a forgotten password or administrative action.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#UserAccountPasswordResetEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#UserAccountPasswordResetEvent(User<br>account<br>password<br>reset<br>event):::d3fend-->d3fend.owl#UserAccountEvent
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
- [User account password reset event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/User%20account%20event/User%20account%20password%20reset%20event/User%20account%20password%20reset%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
