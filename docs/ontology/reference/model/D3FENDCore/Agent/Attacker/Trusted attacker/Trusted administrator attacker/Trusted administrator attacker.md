# Trusted administrator attacker

## Overview

### Definition
A trusted attacker who misuses administrative access to execute attacks, often with elevated privileges.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#TrustedAdministratorAttacker

### Subclass Of
```mermaid
graph BT
    d3fend.owl#TrustedAdministratorAttacker(Trusted<br>administrator<br>attacker):::d3fend-->d3fend.owl#TrustedAttacker
    d3fend.owl#TrustedAttacker(Trusted<br>attacker):::d3fend-->d3fend.owl#Attacker
    d3fend.owl#Attacker(Attacker):::d3fend-->d3fend.owl#Agent
    d3fend.owl#Agent(Agent):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Agent](/docs/ontology/reference/model/D3FENDCore/Agent/Agent.md)
- [Attacker](/docs/ontology/reference/model/D3FENDCore/Agent/Attacker/Attacker.md)
- [Trusted attacker](/docs/ontology/reference/model/D3FENDCore/Agent/Attacker/Trusted%20attacker/Trusted%20attacker.md)
- [Trusted administrator attacker](/docs/ontology/reference/model/D3FENDCore/Agent/Attacker/Trusted%20attacker/Trusted%20administrator%20attacker/Trusted%20administrator%20attacker.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
