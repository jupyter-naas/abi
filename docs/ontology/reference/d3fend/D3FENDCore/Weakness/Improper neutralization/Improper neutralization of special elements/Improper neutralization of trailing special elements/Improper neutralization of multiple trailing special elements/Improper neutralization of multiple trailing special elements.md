# Improper neutralization of multiple trailing special elements

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-163

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-163(Improper<br>neutralization<br>of<br>multiple<br>trailing<br>special<br>elements):::d3fend-->d3fend.owl#CWE-162
    d3fend.owl#CWE-162(Improper<br>neutralization<br>of<br>trailing<br>special<br>elements):::d3fend-->d3fend.owl#CWE-138
    d3fend.owl#CWE-138(Improper<br>neutralization<br>of<br>special<br>elements):::d3fend-->d3fend.owl#CWE-707
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
- [Improper neutralization of special elements](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization%20of%20special%20elements/Improper%20neutralization%20of%20special%20elements.md)
- [Improper neutralization of trailing special elements](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization%20of%20special%20elements/Improper%20neutralization%20of%20trailing%20special%20elements/Improper%20neutralization%20of%20trailing%20special%20elements.md)
- [Improper neutralization of multiple trailing special elements](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization%20of%20special%20elements/Improper%20neutralization%20of%20trailing%20special%20elements/Improper%20neutralization%20of%20multiple%20trailing%20special%20elements/Improper%20neutralization%20of%20multiple%20trailing%20special%20elements.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

