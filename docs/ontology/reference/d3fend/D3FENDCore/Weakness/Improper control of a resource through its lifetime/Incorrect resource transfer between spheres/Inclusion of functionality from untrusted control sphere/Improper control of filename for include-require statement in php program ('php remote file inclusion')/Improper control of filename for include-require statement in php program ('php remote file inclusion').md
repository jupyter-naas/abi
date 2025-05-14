# Improper control of filename for include/require statement in php program ('php remote file inclusion')

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-98

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-98(Improper<br>control<br>of<br>filename<br>for<br>include-require<br>statement<br>in<br>php<br>program<br>('php<br>remote<br>file<br>inclusion')):::d3fend-->d3fend.owl#CWE-829
    d3fend.owl#CWE-829(Inclusion<br>of<br>functionality<br>from<br>untrusted<br>control<br>sphere):::d3fend-->d3fend.owl#CWE-669
    d3fend.owl#CWE-669(Incorrect<br>resource<br>transfer<br>between<br>spheres):::d3fend-->d3fend.owl#CWE-664
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
- [Incorrect resource transfer between spheres](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20resource%20transfer%20between%20spheres/Incorrect%20resource%20transfer%20between%20spheres.md)
- [Inclusion of functionality from untrusted control sphere](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20resource%20transfer%20between%20spheres/Inclusion%20of%20functionality%20from%20untrusted%20control%20sphere/Inclusion%20of%20functionality%20from%20untrusted%20control%20sphere.md)
- [Improper control of filename for include-require statement in php program ('php remote file inclusion')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20resource%20transfer%20between%20spheres/Inclusion%20of%20functionality%20from%20untrusted%20control%20sphere/Improper%20control%20of%20filename%20for%20include-require%20statement%20in%20php%20program%20%28%27php%20remote%20file%20inclusion%27%29/Improper%20control%20of%20filename%20for%20include-require%20statement%20in%20php%20program%20%28%27php%20remote%20file%20inclusion%27%29.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

