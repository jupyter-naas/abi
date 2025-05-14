# Ejb bad practices: use of synchronization primitives

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-574

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-574(Ejb<br>bad<br>practices:<br>use<br>of<br>synchronization<br>primitives):::d3fend-->d3fend.owl#CWE-695
    d3fend.owl#CWE-695(Use<br>of<br>low-level<br>functionality):::d3fend-->d3fend.owl#CWE-573
    d3fend.owl#CWE-573(Improper<br>following<br>of<br>specification<br>by<br>caller):::d3fend-->d3fend.owl#CWE-710
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
- [Improper following of specification by caller](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Improper%20following%20of%20specification%20by%20caller.md)
- [Use of low-level functionality](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Use%20of%20low-level%20functionality/Use%20of%20low-level%20functionality.md)
- [Ejb bad practices: use of synchronization primitives](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Use%20of%20low-level%20functionality/Ejb%20bad%20practices%3A%20use%20of%20synchronization%20primitives/Ejb%20bad%20practices%3A%20use%20of%20synchronization%20primitives.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

