# Exposed ioctl with insufficient access control

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-782

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-782(Exposed<br>ioctl<br>with<br>insufficient<br>access<br>control):::d3fend-->d3fend.owl#CWE-749
    d3fend.owl#CWE-749(Exposed<br>dangerous<br>method<br>or<br>function):::d3fend-->d3fend.owl#CWE-284
    d3fend.owl#CWE-284(Improper<br>access<br>control):::d3fend-->d3fend.owl#Weakness
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
- [Improper access control](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20access%20control.md)
- [Exposed dangerous method or function](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Exposed%20dangerous%20method%20or%20function/Exposed%20dangerous%20method%20or%20function.md)
- [Exposed ioctl with insufficient access control](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Exposed%20dangerous%20method%20or%20function/Exposed%20ioctl%20with%20insufficient%20access%20control/Exposed%20ioctl%20with%20insufficient%20access%20control.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

