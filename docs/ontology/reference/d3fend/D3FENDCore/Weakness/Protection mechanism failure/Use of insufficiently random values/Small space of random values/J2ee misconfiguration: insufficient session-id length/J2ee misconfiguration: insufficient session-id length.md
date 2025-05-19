# J2ee misconfiguration: insufficient session-id length

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-6

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-6(J2ee<br>misconfiguration:<br>insufficient<br>session-id<br>length):::d3fend-->d3fend.owl#CWE-334
    d3fend.owl#CWE-334(Small<br>space<br>of<br>random<br>values):::d3fend-->d3fend.owl#CWE-330
    d3fend.owl#CWE-330(Use<br>of<br>insufficiently<br>random<br>values):::d3fend-->d3fend.owl#CWE-693
    d3fend.owl#CWE-693(Protection<br>mechanism<br>failure):::d3fend-->d3fend.owl#Weakness
    d3fend.owl#Weakness(Weakness):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md)
- [Protection mechanism failure](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Protection%20mechanism%20failure.md)
- [Use of insufficiently random values](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Use%20of%20insufficiently%20random%20values/Use%20of%20insufficiently%20random%20values.md)
- [Small space of random values](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Use%20of%20insufficiently%20random%20values/Small%20space%20of%20random%20values/Small%20space%20of%20random%20values.md)
- [J2ee misconfiguration: insufficient session-id length](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Use%20of%20insufficiently%20random%20values/Small%20space%20of%20random%20values/J2ee%20misconfiguration%3A%20insufficient%20session-id%20length/J2ee%20misconfiguration%3A%20insufficient%20session-id%20length.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

