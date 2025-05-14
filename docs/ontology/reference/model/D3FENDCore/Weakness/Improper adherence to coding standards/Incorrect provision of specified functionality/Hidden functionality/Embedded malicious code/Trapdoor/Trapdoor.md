# Trapdoor

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-510

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-510(Trapdoor):::d3fend-->d3fend.owl#CWE-506
    d3fend.owl#CWE-506(Embedded<br>malicious<br>code):::d3fend-->d3fend.owl#CWE-912
    d3fend.owl#CWE-912(Hidden<br>functionality):::d3fend-->d3fend.owl#CWE-684
    d3fend.owl#CWE-684(Incorrect<br>provision<br>of<br>specified<br>functionality):::d3fend-->d3fend.owl#CWE-710
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
- [Incorrect provision of specified functionality](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Incorrect%20provision%20of%20specified%20functionality/Incorrect%20provision%20of%20specified%20functionality.md)
- [Hidden functionality](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Incorrect%20provision%20of%20specified%20functionality/Hidden%20functionality/Hidden%20functionality.md)
- [Embedded malicious code](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Incorrect%20provision%20of%20specified%20functionality/Hidden%20functionality/Embedded%20malicious%20code/Embedded%20malicious%20code.md)
- [Trapdoor](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Incorrect%20provision%20of%20specified%20functionality/Hidden%20functionality/Embedded%20malicious%20code/Trapdoor/Trapdoor.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

