# Comparison of object references instead of object contents

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-595

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-595(Comparison<br>of<br>object<br>references<br>instead<br>of<br>object<br>contents):::d3fend-->d3fend.owl#CWE-1025
    d3fend.owl#CWE-1025(Comparison<br>using<br>wrong<br>factors):::d3fend-->d3fend.owl#CWE-697
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
- [Comparison using wrong factors](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20comparison/Comparison%20using%20wrong%20factors/Comparison%20using%20wrong%20factors.md)
- [Comparison of object references instead of object contents](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20comparison/Comparison%20using%20wrong%20factors/Comparison%20of%20object%20references%20instead%20of%20object%20contents/Comparison%20of%20object%20references%20instead%20of%20object%20contents.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

