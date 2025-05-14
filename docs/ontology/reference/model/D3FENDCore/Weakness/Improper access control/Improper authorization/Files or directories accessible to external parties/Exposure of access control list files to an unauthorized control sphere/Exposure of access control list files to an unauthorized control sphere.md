# Exposure of access control list files to an unauthorized control sphere

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-529

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-529(Exposure<br>of<br>access<br>control<br>list<br>files<br>to<br>an<br>unauthorized<br>control<br>sphere):::d3fend-->d3fend.owl#CWE-552
    d3fend.owl#CWE-552(Files<br>or<br>directories<br>accessible<br>to<br>external<br>parties):::d3fend-->d3fend.owl#CWE-285
    d3fend.owl#CWE-285(Improper<br>authorization):::d3fend-->d3fend.owl#CWE-284
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
- [Improper authorization](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Improper%20authorization.md)
- [Files or directories accessible to external parties](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Files%20or%20directories%20accessible%20to%20external%20parties/Files%20or%20directories%20accessible%20to%20external%20parties.md)
- [Exposure of access control list files to an unauthorized control sphere](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Files%20or%20directories%20accessible%20to%20external%20parties/Exposure%20of%20access%20control%20list%20files%20to%20an%20unauthorized%20control%20sphere/Exposure%20of%20access%20control%20list%20files%20to%20an%20unauthorized%20control%20sphere.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

