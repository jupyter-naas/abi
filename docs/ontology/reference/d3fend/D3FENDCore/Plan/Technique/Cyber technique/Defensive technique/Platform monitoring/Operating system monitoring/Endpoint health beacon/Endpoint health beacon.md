# Endpoint health beacon

## Overview

### Definition
Monitoring the security status of an endpoint by sending periodic messages with health status, where absence of a response may indicate that the endpoint has been compromised.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#EndpointHealthBeacon

### Subclass Of
```mermaid
graph BT
    d3fend.owl#EndpointHealthBeacon(Endpoint<br>health<br>beacon):::d3fend-->d3fend.owl#OperatingSystemMonitoring
    d3fend.owl#OperatingSystemMonitoring(Operating<br>system<br>monitoring):::d3fend-->d3fend.owl#PlatformMonitoring
    d3fend.owl#PlatformMonitoring(Platform<br>monitoring):::d3fend-->d3fend.owl#DefensiveTechnique
    d3fend.owl#DefensiveTechnique(Defensive<br>technique):::d3fend-->d3fend.owl#CyberTechnique
    d3fend.owl#CyberTechnique(Cyber<br>technique):::d3fend-->d3fend.owl#Technique
    d3fend.owl#Technique(Technique):::d3fend-->d3fend.owl#Plan
    d3fend.owl#Plan(Plan):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Plan](/docs/ontology/reference/model/D3FENDCore/Plan/Plan.md)
- [Technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Technique.md)
- [Cyber technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Cyber%20technique.md)
- [Defensive technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Defensive%20technique.md)
- [Platform monitoring](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Platform%20monitoring/Platform%20monitoring.md)
- [Operating system monitoring](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Platform%20monitoring/Operating%20system%20monitoring/Operating%20system%20monitoring.md)
- [Endpoint health beacon](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Platform%20monitoring/Operating%20system%20monitoring/Endpoint%20health%20beacon/Endpoint%20health%20beacon.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
