# Dhcp release event

## Overview

### Definition
An event where a DHCP client sends a RELEASE message to relinquish its assigned IP address and cancel any remaining lease duration.

### Examples
Not defined.

### Aliases
DHCPRELEASE

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#DHCPReleaseEvent

### Subclass Of
```mermaid
graph BT
    d3fend.owl#DHCPReleaseEvent(Dhcp<br>release<br>event):::d3fend-->d3fend.owl#DHCPEvent
    d3fend.owl#DHCPEvent(Dhcp<br>event):::d3fend-->d3fend.owl#ApplicationLayerEvent
    d3fend.owl#ApplicationLayerEvent(Application<br>layer<br>event):::d3fend-->d3fend.owl#NetworkEvent
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
- [Application layer event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Application%20layer%20event/Application%20layer%20event.md)
- [Dhcp event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Application%20layer%20event/Dhcp%20event/Dhcp%20event.md)
- [Dhcp release event](/docs/ontology/reference/model/D3FENDCore/Event/Digital%20event/Network%20event/Application%20layer%20event/Dhcp%20event/Dhcp%20release%20event/Dhcp%20release%20event.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
