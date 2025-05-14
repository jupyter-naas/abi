# Use of getlogin() in multithreaded application

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-558

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-558(Use<br>of<br>getlogin()<br>in<br>multithreaded<br>application):::d3fend-->d3fend.owl#CWE-663
    d3fend.owl#CWE-663(Use<br>of<br>a<br>non-reentrant<br>function<br>in<br>a<br>concurrent<br>context):::d3fend-->d3fend.owl#CWE-662
    d3fend.owl#CWE-662(Improper<br>synchronization):::d3fend-->d3fend.owl#CWE-691
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
- [Improper synchronization](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Improper%20synchronization/Improper%20synchronization.md)
- [Use of a non-reentrant function in a concurrent context](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Improper%20synchronization/Use%20of%20a%20non-reentrant%20function%20in%20a%20concurrent%20context/Use%20of%20a%20non-reentrant%20function%20in%20a%20concurrent%20context.md)
- [Use of getlogin() in multithreaded application](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Improper%20synchronization/Use%20of%20a%20non-reentrant%20function%20in%20a%20concurrent%20context/Use%20of%20getlogin%28%29%20in%20multithreaded%20application/Use%20of%20getlogin%28%29%20in%20multithreaded%20application.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

