# Use of wrong operator in string comparison

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-597

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-597(Use<br>of<br>wrong<br>operator<br>in<br>string<br>comparison):::d3fend-->d3fend.owl#CWE-480
    d3fend.owl#CWE-480(Use<br>of<br>incorrect<br>operator):::d3fend-->d3fend.owl#CWE-670
    d3fend.owl#CWE-670(Always-incorrect<br>control<br>flow<br>implementation):::d3fend-->d3fend.owl#CWE-691
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
- [Always-incorrect control flow implementation](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Always-incorrect%20control%20flow%20implementation/Always-incorrect%20control%20flow%20implementation.md)
- [Use of incorrect operator](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Always-incorrect%20control%20flow%20implementation/Use%20of%20incorrect%20operator/Use%20of%20incorrect%20operator.md)
- [Use of wrong operator in string comparison](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Always-incorrect%20control%20flow%20implementation/Use%20of%20incorrect%20operator/Use%20of%20wrong%20operator%20in%20string%20comparison/Use%20of%20wrong%20operator%20in%20string%20comparison.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

