# Predictable value range from previous values

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-343

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-343(Predictable<br>value<br>range<br>from<br>previous<br>values):::d3fend-->d3fend.owl#CWE-340
    d3fend.owl#CWE-340(Generation<br>of<br>predictable<br>numbers<br>or<br>identifiers):::d3fend-->d3fend.owl#CWE-330
    d3fend.owl#CWE-330(Use<br>of<br>insufficiently<br>random<br>values):::d3fend-->d3fend.owl#CWE-693
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
- [Use of insufficiently random values](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Use%20of%20insufficiently%20random%20values/Use%20of%20insufficiently%20random%20values.md)
- [Generation of predictable numbers or identifiers](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Use%20of%20insufficiently%20random%20values/Generation%20of%20predictable%20numbers%20or%20identifiers/Generation%20of%20predictable%20numbers%20or%20identifiers.md)
- [Predictable value range from previous values](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Use%20of%20insufficiently%20random%20values/Generation%20of%20predictable%20numbers%20or%20identifiers/Predictable%20value%20range%20from%20previous%20values/Predictable%20value%20range%20from%20previous%20values.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

