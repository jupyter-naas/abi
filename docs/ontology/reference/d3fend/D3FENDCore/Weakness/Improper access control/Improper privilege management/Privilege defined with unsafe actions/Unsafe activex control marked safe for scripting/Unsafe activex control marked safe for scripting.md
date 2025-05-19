# Unsafe activex control marked safe for scripting

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-623

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-623(Unsafe<br>activex<br>control<br>marked<br>safe<br>for<br>scripting):::d3fend-->d3fend.owl#CWE-267
    d3fend.owl#CWE-267(Privilege<br>defined<br>with<br>unsafe<br>actions):::d3fend-->d3fend.owl#CWE-269
    d3fend.owl#CWE-269(Improper<br>privilege<br>management):::d3fend-->d3fend.owl#CWE-284
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
- [Improper privilege management](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20privilege%20management/Improper%20privilege%20management.md)
- [Privilege defined with unsafe actions](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20privilege%20management/Privilege%20defined%20with%20unsafe%20actions/Privilege%20defined%20with%20unsafe%20actions.md)
- [Unsafe activex control marked safe for scripting](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20privilege%20management/Privilege%20defined%20with%20unsafe%20actions/Unsafe%20activex%20control%20marked%20safe%20for%20scripting/Unsafe%20activex%20control%20marked%20safe%20for%20scripting.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

