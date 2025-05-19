# Logon event

## Overview

### Definition
An authentication event where a new session is initiated, signifying the successful validation of credentials and establishment of an authorized connection to a system, application, or resource. This marks the beginning of the subject’s authenticated interaction with the system.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#LogonEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#LogonEvent(Logon<br>event):::d3fend-->d3fend.owl#AuthenticationEvent
    d3fend.owl#AuthenticationEvent(Authentication<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Authentication event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Authentication%20event/Authentication%20event.md)
- [Logon event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Authentication%20event/Logon%20event/Logon%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
