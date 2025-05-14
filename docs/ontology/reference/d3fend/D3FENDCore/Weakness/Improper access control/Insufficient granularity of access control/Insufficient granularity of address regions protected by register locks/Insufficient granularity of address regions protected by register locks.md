# Insufficient granularity of address regions protected by register locks

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1222

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1222(Insufficient<br>granularity<br>of<br>address<br>regions<br>protected<br>by<br>register<br>locks):::d3fend-->d3fend.owl#CWE-1220
    d3fend.owl#CWE-1220(Insufficient<br>granularity<br>of<br>access<br>control):::d3fend-->d3fend.owl#CWE-284
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
- [Insufficient granularity of access control](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Insufficient%20granularity%20of%20access%20control/Insufficient%20granularity%20of%20access%20control.md)
- [Insufficient granularity of address regions protected by register locks](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Insufficient%20granularity%20of%20access%20control/Insufficient%20granularity%20of%20address%20regions%20protected%20by%20register%20locks/Insufficient%20granularity%20of%20address%20regions%20protected%20by%20register%20locks.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

