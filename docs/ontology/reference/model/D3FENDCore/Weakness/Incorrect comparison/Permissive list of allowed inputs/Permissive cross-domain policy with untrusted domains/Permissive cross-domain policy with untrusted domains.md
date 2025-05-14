# Permissive cross-domain policy with untrusted domains

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-942

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-942(Permissive<br>cross-domain<br>policy<br>with<br>untrusted<br>domains):::d3fend-->d3fend.owl#CWE-183
    d3fend.owl#CWE-183(Permissive<br>list<br>of<br>allowed<br>inputs):::d3fend-->d3fend.owl#CWE-697
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
- [Permissive list of allowed inputs](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20comparison/Permissive%20list%20of%20allowed%20inputs/Permissive%20list%20of%20allowed%20inputs.md)
- [Permissive cross-domain policy with untrusted domains](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20comparison/Permissive%20list%20of%20allowed%20inputs/Permissive%20cross-domain%20policy%20with%20untrusted%20domains/Permissive%20cross-domain%20policy%20with%20untrusted%20domains.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

