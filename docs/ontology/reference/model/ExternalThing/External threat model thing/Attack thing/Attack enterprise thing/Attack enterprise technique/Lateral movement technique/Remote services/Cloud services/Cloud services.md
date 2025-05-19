# Cloud services

## Overview

### Definition
Adversaries may log into accessible cloud services within a compromised environment using [Valid Accounts](https://attack.mitre.org/techniques/T1078) that are synchronized with or federated to on-premises user identities. The adversary may then perform management actions or access cloud-hosted resources as the logged-on user.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#T1021.007

### Subclass Of
```mermaid
graph BT
    d3fend.owl#T1021.007(Cloud<br>services):::d3fend-->d3fend.owl#T1021
    d3fend.owl#T1021(Remote<br>services):::d3fend-->d3fend.owl#LateralMovementTechnique
    d3fend.owl#LateralMovementTechnique(Lateral<br>movement<br>technique):::d3fend-->d3fend.owl#ATTACKEnterpriseTechnique
    d3fend.owl#ATTACKEnterpriseTechnique(Attack<br>enterprise<br>technique):::d3fend-->d3fend.owl#ATTACKEnterpriseThing
    d3fend.owl#ATTACKEnterpriseThing(Attack<br>enterprise<br>thing):::d3fend-->d3fend.owl#ATTACKThing
    d3fend.owl#ATTACKThing(Attack<br>thing):::d3fend-->d3fend.owl#ExternalThreatModelThing
    d3fend.owl#ExternalThreatModelThing(External<br>threat<br>model<br>thing):::d3fend-->d3fend.owl#ExternalThing
    d3fend.owl#ExternalThing(ExternalThing):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [ExternalThing](/docs/ontology/reference/model/ExternalThing/ExternalThing.md)
- [External threat model thing](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/External%20threat%20model%20thing.md)
- [Attack thing](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20thing.md)
- [Attack enterprise thing](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20thing.md)
- [Attack enterprise technique](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Attack%20enterprise%20technique.md)
- [Lateral movement technique](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Lateral%20movement%20technique/Lateral%20movement%20technique.md)
- [Remote services](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Lateral%20movement%20technique/Remote%20services/Remote%20services.md)
- [Cloud services](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Lateral%20movement%20technique/Remote%20services/Cloud%20services/Cloud%20services.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
