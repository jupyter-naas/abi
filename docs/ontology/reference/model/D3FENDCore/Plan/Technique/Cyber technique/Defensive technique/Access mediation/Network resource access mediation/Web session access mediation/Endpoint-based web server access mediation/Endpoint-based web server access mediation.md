# Endpoint-based web server access mediation

## Overview

### Definition
Endpoint-based web server access mediation regulates web server access directly from user endpoints by implementing mechanisms such as client-side certificates and endpoint security software to authenticate devices and ensure compliant access.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#EndpointBasedWebServerAccessMediation

### Subclass Of
```mermaid
graph BT
    d3fend.owl#EndpointBasedWebServerAccessMediation(Endpoint-based<br>web<br>server<br>access<br>mediation):::d3fend-->d3fend.owl#WebSessionAccessMediation
    d3fend.owl#WebSessionAccessMediation(Web<br>session<br>access<br>mediation):::d3fend-->d3fend.owl#NetworkResourceAccessMediation
    d3fend.owl#NetworkResourceAccessMediation(Network<br>resource<br>access<br>mediation):::d3fend-->d3fend.owl#AccessMediation
    d3fend.owl#AccessMediation(Access<br>mediation):::d3fend-->d3fend.owl#DefensiveTechnique
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
- [Access mediation](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Access%20mediation/Access%20mediation.md)
- [Network resource access mediation](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Access%20mediation/Network%20resource%20access%20mediation/Network%20resource%20access%20mediation.md)
- [Web session access mediation](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Access%20mediation/Network%20resource%20access%20mediation/Web%20session%20access%20mediation/Web%20session%20access%20mediation.md)
- [Endpoint-based web server access mediation](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Access%20mediation/Network%20resource%20access%20mediation/Web%20session%20access%20mediation/Endpoint-based%20web%20server%20access%20mediation/Endpoint-based%20web%20server%20access%20mediation.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
