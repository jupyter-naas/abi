# Ssh listen event

## Overview

### Definition
An event indicating that an SSH server has started listening for incoming connection requests, enabling potential clients to initiate secure sessions.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#SSHListenEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#SSHListenEvent(Ssh<br>listen<br>event):::d3fend-->d3fend.owl#NetworkConnectionListenEvent
    d3fend.owl#NetworkConnectionListenEvent(Network<br>connection<br>listen<br>event):::d3fend-->d3fend.owl#NetworkConnectionEvent
    d3fend.owl#NetworkConnectionEvent(Network<br>connection<br>event):::d3fend-->d3fend.owl#NetworkEvent
    d3fend.owl#NetworkEvent(Network<br>event):::d3fend-->d3fend.owl#DigitalEvent
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
- [Network event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Network%20event.md)
- [Network connection event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Network%20connection%20event/Network%20connection%20event.md)
- [Network connection listen event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Network%20connection%20event/Network%20connection%20listen%20event/Network%20connection%20listen%20event.md)
- [Ssh listen event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Network%20connection%20event/Network%20connection%20listen%20event/Ssh%20listen%20event/Ssh%20listen%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
