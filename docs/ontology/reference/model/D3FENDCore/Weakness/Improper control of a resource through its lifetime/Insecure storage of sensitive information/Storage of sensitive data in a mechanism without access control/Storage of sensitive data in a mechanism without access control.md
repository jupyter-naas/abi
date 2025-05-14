# Storage of sensitive data in a mechanism without access control

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-921

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-921(Storage<br>of<br>sensitive<br>data<br>in<br>a<br>mechanism<br>without<br>access<br>control):::d3fend-->d3fend.owl#CWE-922
    d3fend.owl#CWE-922(Insecure<br>storage<br>of<br>sensitive<br>information):::d3fend-->d3fend.owl#CWE-664
    d3fend.owl#CWE-664(Improper<br>control<br>of<br>a<br>resource<br>through<br>its<br>lifetime):::d3fend-->d3fend.owl#Weakness
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
- [Improper control of a resource through its lifetime](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20control%20of%20a%20resource%20through%20its%20lifetime.md)
- [Insecure storage of sensitive information](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Insecure%20storage%20of%20sensitive%20information/Insecure%20storage%20of%20sensitive%20information.md)
- [Storage of sensitive data in a mechanism without access control](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Insecure%20storage%20of%20sensitive%20information/Storage%20of%20sensitive%20data%20in%20a%20mechanism%20without%20access%20control/Storage%20of%20sensitive%20data%20in%20a%20mechanism%20without%20access%20control.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

