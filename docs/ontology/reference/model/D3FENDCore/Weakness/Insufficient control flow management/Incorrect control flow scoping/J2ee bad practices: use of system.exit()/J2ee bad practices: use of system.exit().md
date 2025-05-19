# J2ee bad practices: use of system.exit()

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-382

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-382(J2ee<br>bad<br>practices:<br>use<br>of<br>system.exit()):::d3fend-->d3fend.owl#CWE-705
    d3fend.owl#CWE-705(Incorrect<br>control<br>flow<br>scoping):::d3fend-->d3fend.owl#CWE-691
    d3fend.owl#CWE-691(Insufficient<br>control<br>flow<br>management):::d3fend-->d3fend.owl#Weakness
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
- [Insufficient control flow management](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Insufficient%20control%20flow%20management.md)
- [Incorrect control flow scoping](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Incorrect%20control%20flow%20scoping/Incorrect%20control%20flow%20scoping.md)
- [J2ee bad practices: use of system.exit()](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Incorrect%20control%20flow%20scoping/J2ee%20bad%20practices%3A%20use%20of%20system.exit%28%29/J2ee%20bad%20practices%3A%20use%20of%20system.exit%28%29.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

