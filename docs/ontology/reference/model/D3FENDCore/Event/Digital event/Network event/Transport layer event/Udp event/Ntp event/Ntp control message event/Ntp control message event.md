# Ntp control message event

## Overview

### Definition
An event where an NTP client or server exchanges control messages used for diagnostic, monitoring, or administrative management of the NTP protocol, rather than time synchronization.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#NTPControlMessageEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#NTPControlMessageEvent(Ntp<br>control<br>message<br>event):::d3fend-->d3fend.owl#NTPEvent
    d3fend.owl#NTPEvent(Ntp<br>event):::d3fend-->d3fend.owl#UDPEvent
    d3fend.owl#UDPEvent(Udp<br>event):::d3fend-->d3fend.owl#TransportLayerEvent
    d3fend.owl#TransportLayerEvent(Transport<br>layer<br>event):::d3fend-->d3fend.owl#NetworkEvent
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
- [Transport layer event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Transport%20layer%20event/Transport%20layer%20event.md)
- [Udp event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Transport%20layer%20event/Udp%20event/Udp%20event.md)
- [Ntp event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Transport%20layer%20event/Udp%20event/Ntp%20event/Ntp%20event.md)
- [Ntp control message event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Transport%20layer%20event/Udp%20event/Ntp%20event/Ntp%20control%20message%20event/Ntp%20control%20message%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
