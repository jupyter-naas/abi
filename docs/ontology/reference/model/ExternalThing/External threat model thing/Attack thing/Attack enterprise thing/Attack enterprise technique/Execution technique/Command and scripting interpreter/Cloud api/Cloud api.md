# Cloud api

## Overview

### Definition
Adversaries may abuse cloud APIs to execute malicious commands. APIs available in cloud environments provide various functionalities and are a feature-rich method for programmatic access to nearly all aspects of a tenant. These APIs may be utilized through various methods such as command line interpreters (CLIs), in-browser Cloud Shells, [PowerShell](https://attack.mitre.org/techniques/T1059/001) modules like Azure for PowerShell(Citation: Microsoft - Azure PowerShell), or software developer kits (SDKs) available for languages such as [Python](https://attack.mitre.org/techniques/T1059/006).

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#T1059.009

### Subclass Of
```mermaid
graph BT
    d3fend.owl#T1059.009(Cloud<br>api):::d3fend-->d3fend.owl#T1059
    d3fend.owl#T1059(Command<br>and<br>scripting<br>interpreter):::d3fend-->d3fend.owl#ExecutionTechnique
    d3fend.owl#ExecutionTechnique(Execution<br>technique):::d3fend-->d3fend.owl#ATTACKEnterpriseTechnique
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
- [Execution technique](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Execution%20technique/Execution%20technique.md)
- [Command and scripting interpreter](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Execution%20technique/Command%20and%20scripting%20interpreter/Command%20and%20scripting%20interpreter.md)
- [Cloud api](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Execution%20technique/Command%20and%20scripting%20interpreter/Cloud%20api/Cloud%20api.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
