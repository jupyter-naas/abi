# Pass the hash

## Overview

### Definition
Pass the hash (PtH) is a method of authenticating as a user without having access to the user's cleartext password. This method bypasses standard authentication steps that require a cleartext password, moving directly into the portion of the authentication that uses the password hash. In this technique, valid password hashes for the account being used are captured using a Credential Access technique. Captured hashes are used with PtH to authenticate as that user. Once authenticated, PtH may be used to perform actions on local or remote systems.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#T1075

### Subclass Of
```mermaid
graph BT
    d3fend.owl#T1075(Pass<br>the<br>hash):::d3fend-->d3fend.owl#LateralMovementTechnique
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
- [Pass the hash](/docs/ontology/reference/model/ExternalThing/External%20threat%20model%20thing/Attack%20thing/Attack%20enterprise%20thing/Attack%20enterprise%20technique/Lateral%20movement%20technique/Pass%20the%20hash/Pass%20the%20hash.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
