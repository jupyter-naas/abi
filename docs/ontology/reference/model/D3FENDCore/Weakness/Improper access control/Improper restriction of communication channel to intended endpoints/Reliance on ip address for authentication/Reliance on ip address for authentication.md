# Reliance on ip address for authentication

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-291

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-291(Reliance<br>on<br>ip<br>address<br>for<br>authentication):::d3fend-->d3fend.owl#CWE-923
    d3fend.owl#CWE-923(Improper<br>restriction<br>of<br>communication<br>channel<br>to<br>intended<br>endpoints):::d3fend-->d3fend.owl#CWE-284
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
- [Improper restriction of communication channel to intended endpoints](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20restriction%20of%20communication%20channel%20to%20intended%20endpoints/Improper%20restriction%20of%20communication%20channel%20to%20intended%20endpoints.md)
- [Reliance on ip address for authentication](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20restriction%20of%20communication%20channel%20to%20intended%20endpoints/Reliance%20on%20ip%20address%20for%20authentication/Reliance%20on%20ip%20address%20for%20authentication.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

