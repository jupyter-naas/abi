# Improper preservation of permissions

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-281

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-281(Improper<br>preservation<br>of<br>permissions):::d3fend-->d3fend.owl#CWE-732
    d3fend.owl#CWE-732(Incorrect<br>permission<br>assignment<br>for<br>critical<br>resource):::d3fend-->d3fend.owl#CWE-668
    d3fend.owl#CWE-668(Exposure<br>of<br>resource<br>to<br>wrong<br>sphere):::d3fend-->d3fend.owl#CWE-664
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
- [Exposure of resource to wrong sphere](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Exposure%20of%20resource%20to%20wrong%20sphere/Exposure%20of%20resource%20to%20wrong%20sphere.md)
- [Incorrect permission assignment for critical resource](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Exposure%20of%20resource%20to%20wrong%20sphere/Incorrect%20permission%20assignment%20for%20critical%20resource/Incorrect%20permission%20assignment%20for%20critical%20resource.md)
- [Improper preservation of permissions](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Exposure%20of%20resource%20to%20wrong%20sphere/Incorrect%20permission%20assignment%20for%20critical%20resource/Improper%20preservation%20of%20permissions/Improper%20preservation%20of%20permissions.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

