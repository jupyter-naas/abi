# Dhcp offer event

## Overview

### Definition
An event where a DHCP server sends an OFFER message to a client in response to a DISCOVER request, proposing an IP address and associated configuration parameters.

### Examples
Not defined.

### Aliases
DHCPOFFER

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#DHCPOfferEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#DHCPOfferEvent(Dhcp<br>offer<br>event):::d3fend-->d3fend.owl#DHCPEvent
    d3fend.owl#DHCPEvent(Dhcp<br>event):::d3fend-->d3fend.owl#UDPEvent
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
- [Dhcp event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Transport%20layer%20event/Udp%20event/Dhcp%20event/Dhcp%20event.md)
- [Dhcp offer event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Transport%20layer%20event/Udp%20event/Dhcp%20event/Dhcp%20offer%20event/Dhcp%20offer%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
