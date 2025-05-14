# Incomplete list of disallowed inputs

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-184

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-184(Incomplete<br>list<br>of<br>disallowed<br>inputs):::d3fend-->d3fend.owl#CWE-1023
    d3fend.owl#CWE-1023(Incomplete<br>comparison<br>with<br>missing<br>factors):::d3fend-->d3fend.owl#CWE-697
    d3fend.owl#CWE-697(Incorrect<br>comparison):::d3fend-->d3fend.owl#Weakness
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
- [Incorrect comparison](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20comparison/Incorrect%20comparison.md)
- [Incomplete comparison with missing factors](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20comparison/Incomplete%20comparison%20with%20missing%20factors/Incomplete%20comparison%20with%20missing%20factors.md)
- [Incomplete list of disallowed inputs](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20comparison/Incomplete%20comparison%20with%20missing%20factors/Incomplete%20list%20of%20disallowed%20inputs/Incomplete%20list%20of%20disallowed%20inputs.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

