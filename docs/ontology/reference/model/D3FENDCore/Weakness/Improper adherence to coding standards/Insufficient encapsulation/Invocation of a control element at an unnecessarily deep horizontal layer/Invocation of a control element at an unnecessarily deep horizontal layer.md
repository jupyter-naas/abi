# Invocation of a control element at an unnecessarily deep horizontal layer

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1054

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1054(Invocation<br>of<br>a<br>control<br>element<br>at<br>an<br>unnecessarily<br>deep<br>horizontal<br>layer):::d3fend-->d3fend.owl#CWE-1061
    d3fend.owl#CWE-1061(Insufficient<br>encapsulation):::d3fend-->d3fend.owl#CWE-710
    d3fend.owl#CWE-710(Improper<br>adherence<br>to<br>coding<br>standards):::d3fend-->d3fend.owl#Weakness
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
- [Improper adherence to coding standards](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20adherence%20to%20coding%20standards.md)
- [Insufficient encapsulation](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Insufficient%20encapsulation/Insufficient%20encapsulation.md)
- [Invocation of a control element at an unnecessarily deep horizontal layer](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Insufficient%20encapsulation/Invocation%20of%20a%20control%20element%20at%20an%20unnecessarily%20deep%20horizontal%20layer/Invocation%20of%20a%20control%20element%20at%20an%20unnecessarily%20deep%20horizontal%20layer.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

