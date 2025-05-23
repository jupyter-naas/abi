# Power-on of untrusted execution core before enabling fabric access control

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1193

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1193(Power-on<br>of<br>untrusted<br>execution<br>core<br>before<br>enabling<br>fabric<br>access<br>control):::d3fend-->d3fend.owl#CWE-696
    d3fend.owl#CWE-696(Incorrect<br>behavior<br>order):::d3fend-->d3fend.owl#CWE-691
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
- [Incorrect behavior order](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Incorrect%20behavior%20order/Incorrect%20behavior%20order.md)
- [Power-on of untrusted execution core before enabling fabric access control](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Incorrect%20behavior%20order/Power-on%20of%20untrusted%20execution%20core%20before%20enabling%20fabric%20access%20control/Power-on%20of%20untrusted%20execution%20core%20before%20enabling%20fabric%20access%20control.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

