# Unparsed raw web content delivery

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-433

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-433(Unparsed<br>raw<br>web<br>content<br>delivery):::d3fend-->d3fend.owl#CWE-219
    d3fend.owl#CWE-219(Storage<br>of<br>file<br>with<br>sensitive<br>data<br>under<br>web<br>root):::d3fend-->d3fend.owl#CWE-552
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
- [Storage of file with sensitive data under web root](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Files%20or%20directories%20accessible%20to%20external%20parties/Storage%20of%20file%20with%20sensitive%20data%20under%20web%20root/Storage%20of%20file%20with%20sensitive%20data%20under%20web%20root.md)
- [Unparsed raw web content delivery](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20access%20control/Improper%20authorization/Files%20or%20directories%20accessible%20to%20external%20parties/Storage%20of%20file%20with%20sensitive%20data%20under%20web%20root/Unparsed%20raw%20web%20content%20delivery/Unparsed%20raw%20web%20content%20delivery.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

