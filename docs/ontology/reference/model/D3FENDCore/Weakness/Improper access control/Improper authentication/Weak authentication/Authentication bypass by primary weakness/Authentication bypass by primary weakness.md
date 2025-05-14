# Authentication bypass by primary weakness

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-305

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-305(Authentication<br>bypass<br>by<br>primary<br>weakness):::d3fend-->d3fend.owl#CWE-1390
    d3fend.owl#CWE-1390(Weak<br>authentication):::d3fend-->d3fend.owl#CWE-287
    d3fend.owl#CWE-287(Improper<br>authentication):::d3fend-->d3fend.owl#CWE-284
    d3fend.owl#CWE-284(Improper<br>access<br>control):::d3fend-->d3fend.owl#Weakness
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
- [Improper access control](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20access%20control.md)
- [Improper authentication](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Improper%20authentication.md)
- [Weak authentication](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Weak%20authentication/Weak%20authentication.md)
- [Authentication bypass by primary weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Weak%20authentication/Authentication%20bypass%20by%20primary%20weakness/Authentication%20bypass%20by%20primary%20weakness.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

