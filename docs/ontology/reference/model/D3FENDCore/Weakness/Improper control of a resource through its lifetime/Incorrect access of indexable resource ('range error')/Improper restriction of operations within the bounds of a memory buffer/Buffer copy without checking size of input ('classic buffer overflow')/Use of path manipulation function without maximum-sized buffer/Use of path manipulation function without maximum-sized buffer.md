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
    d3fend.owl#CWE-785(Use<br>of<br>path<br>manipulation<br>function<br>without<br>maximum-sized<br>buffer):::d3fend-->d3fend.owl#CWE-120
    d3fend.owl#CWE-120(Buffer<br>copy<br>without<br>checking<br>size<br>of<br>input<br>('classic<br>buffer<br>overflow')):::d3fend-->d3fend.owl#CWE-119
    d3fend.owl#CWE-119(Improper<br>restriction<br>of<br>operations<br>within<br>the<br>bounds<br>of<br>a<br>memory<br>buffer):::d3fend-->d3fend.owl#CWE-118
    d3fend.owl#CWE-118(Incorrect<br>access<br>of<br>indexable<br>resource<br>('range<br>error')):::d3fend-->d3fend.owl#CWE-664
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
- [Incorrect access of indexable resource ('range error')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20access%20of%20indexable%20resource%20%28%27range%20error%27%29/Incorrect%20access%20of%20indexable%20resource%20%28%27range%20error%27%29.md)
- [Improper restriction of operations within the bounds of a memory buffer](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20access%20of%20indexable%20resource%20%28%27range%20error%27%29/Improper%20restriction%20of%20operations%20within%20the%20bounds%20of%20a%20memory%20buffer/Improper%20restriction%20of%20operations%20within%20the%20bounds%20of%20a%20memory%20buffer.md)
- [Buffer copy without checking size of input ('classic buffer overflow')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20access%20of%20indexable%20resource%20%28%27range%20error%27%29/Improper%20restriction%20of%20operations%20within%20the%20bounds%20of%20a%20memory%20buffer/Buffer%20copy%20without%20checking%20size%20of%20input%20%28%27classic%20buffer%20overflow%27%29/Buffer%20copy%20without%20checking%20size%20of%20input%20%28%27classic%20buffer%20overflow%27%29.md)
- [Use of path manipulation function without maximum-sized buffer](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20access%20of%20indexable%20resource%20%28%27range%20error%27%29/Improper%20restriction%20of%20operations%20within%20the%20bounds%20of%20a%20memory%20buffer/Buffer%20copy%20without%20checking%20size%20of%20input%20%28%27classic%20buffer%20overflow%27%29/Use%20of%20path%20manipulation%20function%20without%20maximum-sized%20buffer/Use%20of%20path%20manipulation%20function%20without%20maximum-sized%20buffer.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

