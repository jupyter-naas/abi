# Tunnel open event

## Overview

### Definition
An event where a network tunnel is established, enabling encapsulated communication between endpoints. This marks the initiation of secure or isolated data transport through the tunnel.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#TunnelOpenEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#TunnelOpenEvent(Tunnel<br>open<br>event):::d3fend-->d3fend.owl#TunnelEvent
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
- [Tunnel open event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Tunnel%20event/Tunnel%20open%20event/Tunnel%20open%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
