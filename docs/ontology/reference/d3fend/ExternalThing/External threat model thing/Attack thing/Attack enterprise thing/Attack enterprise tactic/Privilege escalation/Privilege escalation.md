# Privilege escalation

## Overview

### Definition
The adversary is trying to gain higher-level permissions.

Privilege Escalation consists of techniques that adversaries use to gain higher-level permissions on a system or network. Adversaries can often enter and explore a network with unprivileged access but require elevated permissions to follow through on their objectives. Common approaches are to take advantage of system weaknesses, misconfigurations, and vulnerabilities. Examples of elevated access include:

SYSTEM/root level
local administrator
user account with admin-like access
user accounts with access to specific system or perform specific function

These techniques often overlap with Persistence techniques, as OS features that let an adversary persist can execute in an elevated context.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#TA0004

### Subclass Of
```mermaid
graph BT
    d3fend.owl#TA0004(Privilege<br>escalation):::d3fend-->d3fend.owl#ATTACKEnterpriseTactic
    d3fend.owl#ATTACKEnterpriseTactic(Attack<br>enterprise<br>tactic):::d3fend-->d3fend.owl#ATTACKEnterpriseThing
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
- [Attack enterprise tactic](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20tactic/Attack%20enterprise%20tactic.md)
- [Privilege escalation](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20tactic/Privilege%20escalation/Privilege%20escalation.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
