# Downgrade system image

## Overview

### Definition
Adversaries may install an older version of the operating system of a network device to weaken security.  Older operating system versions on network devices often have weaker encryption ciphers and, in general, fewer/less updated defensive features. (Citation: Cisco Synful Knock Evolution)

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#T1601.002

### Subclass Of
```mermaid
graph BT
    d3fend.owl#T1601.002(Downgrade<br>system<br>image):::d3fend-->d3fend.owl#T1601
    d3fend.owl#T1601(Modify<br>system<br>image):::d3fend-->d3fend.owl#DefenseEvasionTechnique
    d3fend.owl#DefenseEvasionTechnique(Defense<br>evasion<br>technique):::d3fend-->d3fend.owl#ATTACKEnterpriseTechnique
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
- [Defense evasion technique](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Defense%20evasion%20technique/Defense%20evasion%20technique.md)
- [Modify system image](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Defense%20evasion%20technique/Modify%20system%20image/Modify%20system%20image.md)
- [Downgrade system image](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Defense%20evasion%20technique/Modify%20system%20image/Downgrade%20system%20image/Downgrade%20system%20image.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
