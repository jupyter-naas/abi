# Multiple unlocks of a critical resource

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-765

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-765(Multiple<br>unlocks<br>of<br>a<br>critical<br>resource):::d3fend-->d3fend.owl#CWE-675
    d3fend.owl#CWE-675(Multiple<br>operations<br>on<br>resource<br>in<br>single-operation<br>context):::d3fend-->d3fend.owl#CWE-573
    d3fend.owl#CWE-573(Improper<br>following<br>of<br>specification<br>by<br>caller):::d3fend-->d3fend.owl#CWE-710
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
- [Improper following of specification by caller](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Improper%20following%20of%20specification%20by%20caller.md)
- [Multiple operations on resource in single-operation context](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Multiple%20operations%20on%20resource%20in%20single-operation%20context/Multiple%20operations%20on%20resource%20in%20single-operation%20context.md)
- [Multiple unlocks of a critical resource](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Multiple%20operations%20on%20resource%20in%20single-operation%20context/Multiple%20unlocks%20of%20a%20critical%20resource/Multiple%20unlocks%20of%20a%20critical%20resource.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

