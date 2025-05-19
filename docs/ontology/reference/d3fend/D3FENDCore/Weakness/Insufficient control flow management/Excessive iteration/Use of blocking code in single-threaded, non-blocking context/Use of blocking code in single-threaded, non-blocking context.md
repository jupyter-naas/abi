# Use of blocking code in single-threaded, non-blocking context

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1322

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1322(Use<br>of<br>blocking<br>code<br>in<br>single-threaded,<br>non-blocking<br>context):::d3fend-->d3fend.owl#CWE-834
    d3fend.owl#CWE-834(Excessive<br>iteration):::d3fend-->d3fend.owl#CWE-691
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
- [Excessive iteration](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Excessive%20iteration/Excessive%20iteration.md)
- [Use of blocking code in single-threaded, non-blocking context](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Excessive%20iteration/Use%20of%20blocking%20code%20in%20single-threaded%2C%20non-blocking%20context/Use%20of%20blocking%20code%20in%20single-threaded%2C%20non-blocking%20context.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

