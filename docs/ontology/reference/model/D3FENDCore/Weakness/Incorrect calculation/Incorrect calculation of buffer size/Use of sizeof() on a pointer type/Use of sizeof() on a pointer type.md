# Use of sizeof() on a pointer type

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-467

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-467(Use<br>of<br>sizeof()<br>on<br>a<br>pointer<br>type):::d3fend-->d3fend.owl#CWE-131
    d3fend.owl#CWE-131(Incorrect<br>calculation<br>of<br>buffer<br>size):::d3fend-->d3fend.owl#CWE-682
    d3fend.owl#CWE-682(Incorrect<br>calculation):::d3fend-->d3fend.owl#Weakness
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
- [Incorrect calculation](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20calculation/Incorrect%20calculation.md)
- [Incorrect calculation of buffer size](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20calculation/Incorrect%20calculation%20of%20buffer%20size/Incorrect%20calculation%20of%20buffer%20size.md)
- [Use of sizeof() on a pointer type](/docs/ontology/reference/model/D3FENDCore/Weakness/Incorrect%20calculation/Incorrect%20calculation%20of%20buffer%20size/Use%20of%20sizeof%28%29%20on%20a%20pointer%20type/Use%20of%20sizeof%28%29%20on%20a%20pointer%20type.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

