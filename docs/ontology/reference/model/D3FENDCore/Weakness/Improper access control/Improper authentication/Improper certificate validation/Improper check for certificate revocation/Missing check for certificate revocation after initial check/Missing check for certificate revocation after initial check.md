# Missing check for certificate revocation after initial check

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-370

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-370(Missing<br>check<br>for<br>certificate<br>revocation<br>after<br>initial<br>check):::d3fend-->d3fend.owl#CWE-299
    d3fend.owl#CWE-299(Improper<br>check<br>for<br>certificate<br>revocation):::d3fend-->d3fend.owl#CWE-295
    d3fend.owl#CWE-295(Improper<br>certificate<br>validation):::d3fend-->d3fend.owl#CWE-287
    d3fend.owl#CWE-287(Improper<br>authentication):::d3fend-->d3fend.owl#CWE-284
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
- [Improper authentication](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Improper%20authentication.md)
- [Improper certificate validation](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Improper%20certificate%20validation/Improper%20certificate%20validation.md)
- [Improper check for certificate revocation](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Improper%20certificate%20validation/Improper%20check%20for%20certificate%20revocation/Improper%20check%20for%20certificate%20revocation.md)
- [Missing check for certificate revocation after initial check](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Improper%20certificate%20validation/Improper%20check%20for%20certificate%20revocation/Missing%20check%20for%20certificate%20revocation%20after%20initial%20check/Missing%20check%20for%20certificate%20revocation%20after%20initial%20check.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

