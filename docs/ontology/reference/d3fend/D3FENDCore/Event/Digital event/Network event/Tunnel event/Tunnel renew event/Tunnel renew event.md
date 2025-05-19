# Tunnel renew event

## Overview

### Definition
An event where the lifecycle of a network tunnel is extended, ensuring continued encapsulated communication and avoiding session expiration.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#TunnelRenewEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#TunnelRenewEvent(Tunnel<br>renew<br>event):::d3fend-->d3fend.owl#TunnelEvent
    d3fend.owl#TunnelEvent(Tunnel<br>event):::d3fend-->d3fend.owl#NetworkEvent
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
- [Tunnel event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Tunnel%20event/Tunnel%20event.md)
- [Tunnel renew event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Tunnel%20event/Tunnel%20renew%20event/Tunnel%20renew%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
