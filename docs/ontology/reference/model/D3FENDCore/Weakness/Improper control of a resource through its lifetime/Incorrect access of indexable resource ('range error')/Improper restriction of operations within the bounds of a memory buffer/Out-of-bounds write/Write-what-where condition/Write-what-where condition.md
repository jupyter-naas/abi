# Write-what-where condition

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-123

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-123(Write-what-where<br>condition):::d3fend-->d3fend.owl#CWE-787
    d3fend.owl#CWE-787(Out-of-bounds<br>write):::d3fend-->d3fend.owl#CWE-119
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
- [Out-of-bounds write](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20access%20of%20indexable%20resource%20%28%27range%20error%27%29/Improper%20restriction%20of%20operations%20within%20the%20bounds%20of%20a%20memory%20buffer/Out-of-bounds%20write/Out-of-bounds%20write.md)
- [Write-what-where condition](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Incorrect%20access%20of%20indexable%20resource%20%28%27range%20error%27%29/Improper%20restriction%20of%20operations%20within%20the%20bounds%20of%20a%20memory%20buffer/Out-of-bounds%20write/Write-what-where%20condition/Write-what-where%20condition.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

