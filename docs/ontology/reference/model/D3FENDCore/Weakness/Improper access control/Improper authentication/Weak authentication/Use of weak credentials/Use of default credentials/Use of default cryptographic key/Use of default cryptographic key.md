# Use of default cryptographic key

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1394

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1394(Use<br>of<br>default<br>cryptographic<br>key):::d3fend-->d3fend.owl#CWE-1392
    d3fend.owl#CWE-1392(Use<br>of<br>default<br>credentials):::d3fend-->d3fend.owl#CWE-1391
    d3fend.owl#CWE-1391(Use<br>of<br>weak<br>credentials):::d3fend-->d3fend.owl#CWE-1390
    d3fend.owl#CWE-1390(Weak<br>authentication):::d3fend-->d3fend.owl#CWE-287
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
- [Weak authentication](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Weak%20authentication/Weak%20authentication.md)
- [Use of weak credentials](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Weak%20authentication/Use%20of%20weak%20credentials/Use%20of%20weak%20credentials.md)
- [Use of default credentials](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Weak%20authentication/Use%20of%20weak%20credentials/Use%20of%20default%20credentials/Use%20of%20default%20credentials.md)
- [Use of default cryptographic key](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authentication/Weak%20authentication/Use%20of%20weak%20credentials/Use%20of%20default%20credentials/Use%20of%20default%20cryptographic%20key/Use%20of%20default%20cryptographic%20key.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

