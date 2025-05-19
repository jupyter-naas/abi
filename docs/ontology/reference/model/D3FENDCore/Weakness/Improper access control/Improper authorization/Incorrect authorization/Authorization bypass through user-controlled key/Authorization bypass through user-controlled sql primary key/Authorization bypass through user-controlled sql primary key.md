# Authorization bypass through user-controlled sql primary key

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-566

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-566(Authorization<br>bypass<br>through<br>user-controlled<br>sql<br>primary<br>key):::d3fend-->d3fend.owl#CWE-639
    d3fend.owl#CWE-639(Authorization<br>bypass<br>through<br>user-controlled<br>key):::d3fend-->d3fend.owl#CWE-863
    d3fend.owl#CWE-863(Incorrect<br>authorization):::d3fend-->d3fend.owl#CWE-285
    d3fend.owl#CWE-285(Improper<br>authorization):::d3fend-->d3fend.owl#CWE-284
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
- [Improper authorization](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Improper%20authorization.md)
- [Incorrect authorization](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Incorrect%20authorization/Incorrect%20authorization.md)
- [Authorization bypass through user-controlled key](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Incorrect%20authorization/Authorization%20bypass%20through%20user-controlled%20key/Authorization%20bypass%20through%20user-controlled%20key.md)
- [Authorization bypass through user-controlled sql primary key](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Incorrect%20authorization/Authorization%20bypass%20through%20user-controlled%20key/Authorization%20bypass%20through%20user-controlled%20sql%20primary%20key/Authorization%20bypass%20through%20user-controlled%20sql%20primary%20key.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

