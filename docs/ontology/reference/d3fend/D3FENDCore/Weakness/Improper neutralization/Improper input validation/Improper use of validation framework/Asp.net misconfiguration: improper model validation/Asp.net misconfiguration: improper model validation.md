# Asp.net misconfiguration: improper model validation

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1174

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1174(Asp.net<br>misconfiguration:<br>improper<br>model<br>validation):::d3fend-->d3fend.owl#CWE-1173
    d3fend.owl#CWE-1173(Improper<br>use<br>of<br>validation<br>framework):::d3fend-->d3fend.owl#CWE-20
    d3fend.owl#CWE-20(Improper<br>input<br>validation):::d3fend-->d3fend.owl#CWE-707
    d3fend.owl#CWE-707(Improper<br>neutralization):::d3fend-->d3fend.owl#Weakness
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
- [Improper neutralization](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization.md)
- [Improper input validation](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20input%20validation/Improper%20input%20validation.md)
- [Improper use of validation framework](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20input%20validation/Improper%20use%20of%20validation%20framework/Improper%20use%20of%20validation%20framework.md)
- [Asp.net misconfiguration: improper model validation](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20input%20validation/Improper%20use%20of%20validation%20framework/Asp.net%20misconfiguration%3A%20improper%20model%20validation/Asp.net%20misconfiguration%3A%20improper%20model%20validation.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

