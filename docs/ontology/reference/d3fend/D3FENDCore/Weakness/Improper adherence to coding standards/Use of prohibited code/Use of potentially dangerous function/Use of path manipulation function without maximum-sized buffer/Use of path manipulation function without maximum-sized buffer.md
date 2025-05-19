# Use of path manipulation function without maximum-sized buffer

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-785

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-785(Use<br>of<br>path<br>manipulation<br>function<br>without<br>maximum-sized<br>buffer):::d3fend-->d3fend.owl#CWE-676
    d3fend.owl#CWE-676(Use<br>of<br>potentially<br>dangerous<br>function):::d3fend-->d3fend.owl#CWE-1177
    d3fend.owl#CWE-1177(Use<br>of<br>prohibited<br>code):::d3fend-->d3fend.owl#CWE-710
    d3fend.owl#CWE-710(Improper<br>adherence<br>to<br>coding<br>standards):::d3fend-->d3fend.owl#Weakness
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
- [Improper adherence to coding standards](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20adherence%20to%20coding%20standards.md)
- [Use of prohibited code](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Use%20of%20prohibited%20code/Use%20of%20prohibited%20code.md)
- [Use of potentially dangerous function](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Use%20of%20prohibited%20code/Use%20of%20potentially%20dangerous%20function/Use%20of%20potentially%20dangerous%20function.md)
- [Use of path manipulation function without maximum-sized buffer](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Use%20of%20prohibited%20code/Use%20of%20potentially%20dangerous%20function/Use%20of%20path%20manipulation%20function%20without%20maximum-sized%20buffer/Use%20of%20path%20manipulation%20function%20without%20maximum-sized%20buffer.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

