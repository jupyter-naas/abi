# Expired pointer dereference

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-825

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-825(Expired<br>pointer<br>dereference):::d3fend-->d3fend.owl#CWE-672
    d3fend.owl#CWE-672(Operation<br>on<br>a<br>resource<br>after<br>expiration<br>or<br>release):::d3fend-->d3fend.owl#CWE-666
    d3fend.owl#CWE-666(Operation<br>on<br>resource<br>in<br>wrong<br>phase<br>of<br>lifetime):::d3fend-->d3fend.owl#CWE-664
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
- [Operation on resource in wrong phase of lifetime](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Operation%20on%20resource%20in%20wrong%20phase%20of%20lifetime/Operation%20on%20resource%20in%20wrong%20phase%20of%20lifetime.md)
- [Operation on a resource after expiration or release](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Operation%20on%20resource%20in%20wrong%20phase%20of%20lifetime/Operation%20on%20a%20resource%20after%20expiration%20or%20release/Operation%20on%20a%20resource%20after%20expiration%20or%20release.md)
- [Expired pointer dereference](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Operation%20on%20resource%20in%20wrong%20phase%20of%20lifetime/Operation%20on%20a%20resource%20after%20expiration%20or%20release/Expired%20pointer%20dereference/Expired%20pointer%20dereference.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

