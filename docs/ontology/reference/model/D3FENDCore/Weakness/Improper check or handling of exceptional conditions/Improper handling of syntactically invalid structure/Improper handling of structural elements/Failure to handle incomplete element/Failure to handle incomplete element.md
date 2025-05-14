# Failure to handle incomplete element

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-239

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-239(Failure<br>to<br>handle<br>incomplete<br>element):::d3fend-->d3fend.owl#CWE-237
    d3fend.owl#CWE-237(Improper<br>handling<br>of<br>structural<br>elements):::d3fend-->d3fend.owl#CWE-228
    d3fend.owl#CWE-228(Improper<br>handling<br>of<br>syntactically<br>invalid<br>structure):::d3fend-->d3fend.owl#CWE-703
    d3fend.owl#CWE-703(Improper<br>check<br>or<br>handling<br>of<br>exceptional<br>conditions):::d3fend-->d3fend.owl#Weakness
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
- [Improper check or handling of exceptional conditions](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20check%20or%20handling%20of%20exceptional%20conditions/Improper%20check%20or%20handling%20of%20exceptional%20conditions.md)
- [Improper handling of syntactically invalid structure](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20check%20or%20handling%20of%20exceptional%20conditions/Improper%20handling%20of%20syntactically%20invalid%20structure/Improper%20handling%20of%20syntactically%20invalid%20structure.md)
- [Improper handling of structural elements](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20check%20or%20handling%20of%20exceptional%20conditions/Improper%20handling%20of%20syntactically%20invalid%20structure/Improper%20handling%20of%20structural%20elements/Improper%20handling%20of%20structural%20elements.md)
- [Failure to handle incomplete element](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20check%20or%20handling%20of%20exceptional%20conditions/Improper%20handling%20of%20syntactically%20invalid%20structure/Improper%20handling%20of%20structural%20elements/Failure%20to%20handle%20incomplete%20element/Failure%20to%20handle%20incomplete%20element.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

