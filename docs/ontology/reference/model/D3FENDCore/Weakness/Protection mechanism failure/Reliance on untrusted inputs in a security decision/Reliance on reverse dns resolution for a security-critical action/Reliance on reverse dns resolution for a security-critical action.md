# Reliance on reverse dns resolution for a security-critical action

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-350

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-350(Reliance<br>on<br>reverse<br>dns<br>resolution<br>for<br>a<br>security-critical<br>action):::d3fend-->d3fend.owl#CWE-807
    d3fend.owl#CWE-807(Reliance<br>on<br>untrusted<br>inputs<br>in<br>a<br>security<br>decision):::d3fend-->d3fend.owl#CWE-693
    d3fend.owl#CWE-693(Protection<br>mechanism<br>failure):::d3fend-->d3fend.owl#Weakness
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
- [Protection mechanism failure](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Protection%20mechanism%20failure.md)
- [Reliance on untrusted inputs in a security decision](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Reliance%20on%20untrusted%20inputs%20in%20a%20security%20decision/Reliance%20on%20untrusted%20inputs%20in%20a%20security%20decision.md)
- [Reliance on reverse dns resolution for a security-critical action](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Reliance%20on%20untrusted%20inputs%20in%20a%20security%20decision/Reliance%20on%20reverse%20dns%20resolution%20for%20a%20security-critical%20action/Reliance%20on%20reverse%20dns%20resolution%20for%20a%20security-critical%20action.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

